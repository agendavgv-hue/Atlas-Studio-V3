"""Project workspace — production cards, one-click GENERATE EVERYTHING, progress."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.artifacts import ArtifactKind, ArtifactResolver
from app.pipelines.context import ChannelDefaults
from app.pipelines.image_naming import resolve_images_dir
from app.pipelines.image_progress import ImageQueueProgress
from app.pipelines.results import PipelineOutcome
from app.pipelines.voice_info import voice_file_info
from app.voice.naming import resolve_voice_dir
from app.render.naming import final_video_path, resolve_youtube_dir
from app.render.progress import MovieQueueProgress
from app.thumbnail.naming import resolve_thumbnail_dir, thumbnail_path
from app.thumbnail.progress import ThumbnailQueueProgress
from app.ui.widgets.progress_row import ProgressRow
from app.ui.widgets.voice_player import VoicePlayer

# Comfortable card width so primary/secondary labels stay readable.
_CARD_MIN_WIDTH = 280
_CARD_GAP = 12


class ProjectWorkspacePage(QWidget):
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")
        self._channel_name: str | None = None
        self._project_folder: str | None = None
        self._production_cards: list[QFrame] = []
        self._card_columns = 0

        back_button = QPushButton("← Back to Projects")
        back_button.clicked.connect(self.back_requested.emit)

        top = QHBoxLayout()
        top.addWidget(back_button)
        top.addStretch()

        self._title = QLabel("Project")
        self._title.setObjectName("PageTitle")

        self._meta = QLabel("")
        self._meta.setObjectName("PageSubtitle")

        self._generate_everything = QPushButton("GENERATE EVERYTHING")
        self._generate_everything.setObjectName("PrimaryButton")
        self._generate_everything.setMinimumHeight(48)
        self._generate_everything.clicked.connect(self._start_generate_everything)

        self._cancel_production = QPushButton("Cancel")
        self._cancel_production.setObjectName("SecondaryButton")
        self._cancel_production.setEnabled(False)
        self._cancel_production.clicked.connect(self._cancel_generate_everything)

        one_click_row = QHBoxLayout()
        one_click_row.setSpacing(10)
        one_click_row.addWidget(self._generate_everything, stretch=1)
        one_click_row.addWidget(self._cancel_production)

        # --- Production card ---
        self._generate = QPushButton("Generate Production")
        self._generate.setObjectName("PrimaryButton")
        self._generate.clicked.connect(self._generate_production)

        open_script = QPushButton("Open Script")
        open_script.clicked.connect(lambda: self._open_artifact(ArtifactKind.SCRIPT))

        open_sheet = QPushButton("Open Production Sheet")
        open_sheet.clicked.connect(
            lambda: self._open_artifact(ArtifactKind.PRODUCTION_SHEET)
        )

        self._regen_script = QPushButton("Regenerate Script")
        self._regen_script.setObjectName("SecondaryButton")
        self._regen_script.clicked.connect(self._regenerate_script)

        self._regen_sheet = QPushButton("Regenerate Production Sheet")
        self._regen_sheet.setObjectName("SecondaryButton")
        self._regen_sheet.clicked.connect(self._regenerate_sheet)

        production_card = self._make_card("Script & Sheet")
        production_body = production_card.layout()
        assert isinstance(production_body, QVBoxLayout)
        production_body.addWidget(self._generate)
        production_body.addLayout(self._button_row(open_script, open_sheet))
        production_body.addLayout(self._button_row(self._regen_script, self._regen_sheet))

        # --- Images card ---
        self._generate_images = QPushButton("Generate Images")
        self._generate_images.setObjectName("PrimaryButton")
        self._generate_images.clicked.connect(self._on_images_primary_clicked)

        open_images = QPushButton("Open Folder")
        open_images.clicked.connect(self._open_images_folder)

        self._regen_images = QPushButton("Regenerate Images")
        self._regen_images.setObjectName("SecondaryButton")
        self._regen_images.clicked.connect(self._run_regenerate_images)

        images_card = self._make_card("Images")
        images_body = images_card.layout()
        assert isinstance(images_body, QVBoxLayout)
        images_body.addWidget(self._generate_images)
        images_body.addLayout(self._button_row(open_images, self._regen_images))

        # --- Voice card ---
        self._voice_info = QLabel("No voice file yet")
        self._voice_info.setObjectName("PageSubtitle")
        self._voice_info.setWordWrap(True)
        self._voice_narrator = QLabel("")
        self._voice_narrator.setObjectName("PageSubtitle")
        self._voice_narrator.setWordWrap(True)

        self._generate_voice = QPushButton("Generate Voice")
        self._generate_voice.setObjectName("PrimaryButton")
        self._generate_voice.clicked.connect(self._on_voice_primary_clicked)

        open_voice = QPushButton("Open Folder")
        open_voice.clicked.connect(self._open_voice_folder)

        self._regen_voice = QPushButton("Regenerate Voice")
        self._regen_voice.setObjectName("SecondaryButton")
        self._regen_voice.clicked.connect(self._run_regenerate_voice)

        self._voice_player = VoicePlayer()
        self._voice_player.duration_ready.connect(self._on_voice_duration)

        voice_card = self._make_card("Voice")
        voice_body = voice_card.layout()
        assert isinstance(voice_body, QVBoxLayout)
        voice_body.addWidget(self._voice_info)
        voice_body.addWidget(self._voice_narrator)
        voice_body.addWidget(self._generate_voice)
        voice_body.addLayout(self._button_row(open_voice, self._regen_voice))
        voice_body.addWidget(self._voice_player)

        # --- Movie card ---
        self._generate_movie = QPushButton("Generate Movie")
        self._generate_movie.setObjectName("PrimaryButton")
        self._generate_movie.clicked.connect(self._on_movie_primary_clicked)

        open_movie = QPushButton("Open Folder")
        open_movie.clicked.connect(self._open_movie_folder)

        open_video = QPushButton("Open Video")
        open_video.clicked.connect(self._open_movie_video)

        self._regen_movie = QPushButton("Regenerate Movie")
        self._regen_movie.setObjectName("SecondaryButton")
        self._regen_movie.clicked.connect(self._run_regenerate_movie)

        movie_card = self._make_card("Movie")
        movie_body = movie_card.layout()
        assert isinstance(movie_body, QVBoxLayout)
        movie_body.addWidget(self._generate_movie)
        movie_body.addLayout(
            self._button_row(open_movie, open_video, self._regen_movie)
        )

        # --- Thumbnail card ---
        self._generate_thumbnail = QPushButton("Generate Thumbnail")
        self._generate_thumbnail.setObjectName("PrimaryButton")
        self._generate_thumbnail.clicked.connect(self._on_thumbnail_primary_clicked)

        open_thumbnail = QPushButton("Open Folder")
        open_thumbnail.clicked.connect(self._open_thumbnail_folder)

        open_thumb_file = QPushButton("Open Thumbnail")
        open_thumb_file.clicked.connect(self._open_thumbnail_file)

        self._regen_thumbnail = QPushButton("Regenerate Thumbnail")
        self._regen_thumbnail.setObjectName("SecondaryButton")
        self._regen_thumbnail.clicked.connect(self._run_regenerate_thumbnail)

        thumbnail_card = self._make_card("Thumbnail")
        thumbnail_body = thumbnail_card.layout()
        assert isinstance(thumbnail_body, QVBoxLayout)
        thumbnail_body.addWidget(self._generate_thumbnail)
        thumbnail_body.addLayout(
            self._button_row(open_thumbnail, open_thumb_file, self._regen_thumbnail)
        )

        self._production_cards = [
            production_card,
            images_card,
            voice_card,
            movie_card,
            thumbnail_card,
        ]

        self._cards_host = QWidget()
        self._cards_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._cards_grid = QGridLayout(self._cards_host)
        self._cards_grid.setContentsMargins(0, 0, 0, 0)
        self._cards_grid.setHorizontalSpacing(_CARD_GAP)
        self._cards_grid.setVerticalSpacing(_CARD_GAP)
        self._relayout_production_cards(force=True)

        self._queue = QLabel("")
        self._queue.setObjectName("PageSubtitle")
        self._queue.setWordWrap(True)

        self._result = QLabel("")
        self._result.setObjectName("PageSubtitle")
        self._result.setWordWrap(True)

        progress_label = QLabel("Progress")
        progress_label.setObjectName("SectionLabel")

        self._progress_host = QFrame()
        self._progress_host.setObjectName("ProgressCard")
        self._progress_layout = QVBoxLayout(self._progress_host)
        self._progress_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("ProgressScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self._progress_host)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(self._title)
        layout.addWidget(self._meta)
        layout.addSpacing(8)
        layout.addLayout(one_click_row)
        layout.addSpacing(6)
        layout.addWidget(self._cards_host)
        layout.addWidget(self._queue)
        layout.addWidget(self._result)
        layout.addSpacing(14)
        layout.addWidget(progress_label)
        layout.addWidget(scroll, stretch=1)

        self._connect_tasks()

    @staticmethod
    def _make_card(title: str) -> QFrame:
        card = QFrame()
        card.setObjectName("ProductionCard")
        card.setMinimumWidth(_CARD_MIN_WIDTH)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        body = QVBoxLayout(card)
        body.setContentsMargins(16, 14, 16, 14)
        body.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("ProductionCardTitle")
        body.addWidget(label)
        return card

    @staticmethod
    def _button_row(*buttons: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for button in buttons:
            row.addWidget(button)
        row.addStretch()
        return row

    def _relayout_production_cards(self, *, force: bool = False) -> None:
        width = max(self._cards_host.width(), self.width() - 72)
        if width >= (_CARD_MIN_WIDTH * 3) + (_CARD_GAP * 2):
            columns = 3
        else:
            columns = 2
        if not force and columns == self._card_columns:
            return
        self._card_columns = columns

        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self._cards_host)

        for index, card in enumerate(self._production_cards):
            row = index // columns
            col = index % columns
            self._cards_grid.addWidget(card, row, col)
            card.show()

        for col in range(columns):
            self._cards_grid.setColumnStretch(col, 1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout_production_cards()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._relayout_production_cards(force=True)

    def _connect_tasks(self) -> None:
        app = self._app()
        if app is None:
            return
        app.tasks.image_progress.connect(self._on_image_progress)
        app.tasks.image_finished.connect(self._on_image_finished)
        app.tasks.image_running_changed.connect(self._sync_job_buttons)
        app.tasks.voice_progress.connect(self._on_voice_progress)
        app.tasks.voice_finished.connect(self._on_voice_finished)
        app.tasks.voice_running_changed.connect(self._sync_job_buttons)
        app.tasks.movie_progress.connect(self._on_movie_progress)
        app.tasks.movie_finished.connect(self._on_movie_finished)
        app.tasks.movie_running_changed.connect(self._sync_job_buttons)
        app.tasks.thumbnail_progress.connect(self._on_thumbnail_progress)
        app.tasks.thumbnail_finished.connect(self._on_thumbnail_finished)
        app.tasks.thumbnail_running_changed.connect(self._sync_job_buttons)
        app.generation.running_changed.connect(self._sync_job_buttons)
        app.generation.log_line.connect(self._on_generation_log)
        app.generation.finished.connect(self._on_generation_finished)

    def _start_generate_everything(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.generation.is_running or app.tasks.is_busy:
            self._result.setText("A production job is already running.")
            return
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            self._result.setText(str(exc))
            return

        started = app.generation.start(
            app.production,
            context,
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            self._result.setText("Could not start one-click production.")
            return
        self._voice_player.stop()
        self._queue.setText("One-click production started…")
        self._result.setText("Running full production workflow…")
        self._sync_job_buttons()

    def _cancel_generate_everything(self) -> None:
        app = self._app()
        if app is None:
            return
        if app.generation.is_running and self._is_generation_for_project():
            app.generation.cancel()
            self._queue.setText("Cancelling after current task…")
            self._sync_job_buttons()

    def _on_generation_log(self, line: str) -> None:
        if not self._is_generation_for_project():
            return
        self._queue.setText(line)

    def _on_generation_finished(self, result) -> None:
        if self._channel_name and self._project_folder:
            self.refresh()
        if not self.isVisible():
            self._sync_job_buttons()
            return
        self._show_result(result)
        self._sync_job_buttons()

    def _is_generation_for_project(self) -> bool:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return False
        return app.generation.is_job_for(self._channel_name, self._project_folder)

    def load_project(self, channel_name: str, project_folder: str) -> None:
        self._voice_player.stop()
        self._channel_name = channel_name
        self._project_folder = project_folder
        self.refresh()

    def refresh(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        try:
            project = app.projects.get_project(self._channel_name, self._project_folder)
            progress = app.projects.get_progress(self._channel_name, self._project_folder)
        except (OSError, FileNotFoundError, ValueError):
            self._title.setText("Project not found")
            self._meta.setText("")
            self._clear_progress()
            self._voice_info.setText("No voice file yet")
            self._voice_narrator.setText("")
            self._voice_player.set_source(None)
            return

        self._title.setText(project.name)
        try:
            status = app.projects.lifecycle_status(self._channel_name, self._project_folder)
        except (OSError, FileNotFoundError, ValueError):
            status = project.status
        self._meta.setText(f"{project.channel_name} • {status}")

        self._clear_progress()
        for step in progress.steps:
            self._progress_layout.addWidget(ProgressRow(step.label, step.state))
        self._progress_layout.addStretch()
        self._refresh_voice_panel()
        self._refresh_channel_narrator()
        self._sync_job_buttons()

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _context(self):
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            raise RuntimeError("Project is not open.")
        project = app.projects.get_project(self._channel_name, self._project_folder)
        defaults = ChannelDefaults(name=self._channel_name)
        try:
            channel = app.channels.get_channel(self._channel_name)
            defaults = ChannelDefaults.from_mapping(channel.to_dict(), name=channel.name)
        except (OSError, FileNotFoundError, ValueError):
            pass
        return app.production.build_context(project, defaults)

    def _generate_production(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        self._generate.setEnabled(False)
        self._result.setText("Generating production…")
        app.processEvents()
        try:
            result = app.production.generate_production(self._context())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        finally:
            self._generate.setEnabled(True)

        self._show_result(result)
        self.refresh()

    def _regenerate_script(self) -> None:
        app = self._app()
        if app is None:
            return
        try:
            result = app.production.regenerate_script(self._context())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._show_result(result)
        self.refresh()

    def _regenerate_sheet(self) -> None:
        app = self._app()
        if app is None:
            return
        try:
            result = app.production.regenerate_production_sheet(self._context())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._show_result(result)
        self.refresh()

    def _on_images_primary_clicked(self) -> None:
        app = self._app()
        if app is None:
            return
        if app.tasks.is_images_running and self._is_active_job():
            app.tasks.stop_images()
            self._queue.setText("Stopping after the current image…")
            return
        self._start_images()

    def _run_regenerate_images(self) -> None:
        self._start_images()

    def _start_images(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.tasks.is_busy:
            QMessageBox.information(
                self,
                "Atlas Studio",
                "A background job is already running. Use Stop, or wait for it to finish.",
            )
            return
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return

        started = app.tasks.start_images(
            app.production,
            context,
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            QMessageBox.information(self, "Atlas Studio", "Could not start image generation.")
            return
        self._queue.setText("Starting image queue…")
        self._result.setText("Generating images in background…")
        self._sync_job_buttons()

    def _on_image_progress(self, progress: ImageQueueProgress) -> None:
        if self._is_generation_for_project() or not self._is_active_job():
            return
        elapsed = int(progress.elapsed_seconds)
        minutes, seconds = divmod(elapsed, 60)
        prompt = progress.short_prompt
        parts = [
            progress.message,
            f"{minutes:02d}:{seconds:02d}",
        ]
        if prompt:
            parts.append(prompt)
        self._queue.setText("  ·  ".join(parts))

    def _on_image_finished(self, result) -> None:
        if self._is_generation_for_project():
            return
        if self._channel_name and self._project_folder:
            self.refresh()
        if not self.isVisible():
            self._sync_job_buttons()
            return
        if result.queue_total:
            self._queue.setText(
                f"Queue finished — {result.queue_current}/{result.queue_total}"
                + (
                    f" · failed indexes: {result.failed_indexes}"
                    if result.failed_indexes
                    else ""
                )
            )
        self._show_result(result)
        self._sync_job_buttons()

    def _on_voice_primary_clicked(self) -> None:
        app = self._app()
        if app is None:
            return
        if app.tasks.is_voice_running and self._is_active_job():
            app.tasks.stop_voice()
            self._queue.setText("Stopping voice…")
            return
        self._start_voice()

    def _run_regenerate_voice(self) -> None:
        self._start_voice()

    def _start_voice(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.tasks.is_busy:
            QMessageBox.information(
                self,
                "Atlas Studio",
                "A background job is already running. Use Stop, or wait for it to finish.",
            )
            return
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return

        started = app.tasks.start_voice(
            app.production,
            context,
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            QMessageBox.information(self, "Atlas Studio", "Could not start voice generation.")
            return
        self._voice_player.stop()
        self._queue.setText("Starting voice generation…")
        self._result.setText("Generating voice in background…")
        self._sync_job_buttons()

    def _on_voice_progress(self, progress: VoiceQueueProgress) -> None:
        if self._is_generation_for_project() or not self._is_active_job():
            return
        elapsed = int(progress.elapsed_seconds)
        minutes, seconds = divmod(elapsed, 60)
        parts = [progress.message, f"{minutes:02d}:{seconds:02d}"]
        detail = progress.short_detail
        if detail:
            parts.append(detail)
        self._queue.setText("  ·  ".join(parts))

    def _on_voice_finished(self, result) -> None:
        if self._is_generation_for_project():
            return
        if self._channel_name and self._project_folder:
            self.refresh()
        if not self.isVisible():
            self._sync_job_buttons()
            return
        if result.queue_total:
            self._queue.setText(
                f"Voice finished — {result.queue_current}/{result.queue_total}"
            )
        self._show_result(result)
        self._sync_job_buttons()

    def _on_movie_primary_clicked(self) -> None:
        app = self._app()
        if app is None:
            return
        if app.tasks.is_movie_running and self._is_active_job():
            app.tasks.stop_movie()
            self._queue.setText("Stopping after the current scene…")
            return
        self._start_movie()

    def _run_regenerate_movie(self) -> None:
        self._start_movie()

    def _start_movie(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.tasks.is_busy:
            QMessageBox.information(
                self,
                "Atlas Studio",
                "A background job is already running. Use Stop, or wait for it to finish.",
            )
            return
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return

        started = app.tasks.start_movie(
            app.production,
            context,
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            QMessageBox.information(self, "Atlas Studio", "Could not start movie generation.")
            return
        self._queue.setText("Starting movie render…")
        self._result.setText("Generating movie in background…")
        self._sync_job_buttons()

    def _on_movie_progress(self, progress: MovieQueueProgress) -> None:
        if self._is_generation_for_project() or not self._is_active_job():
            return
        elapsed = int(progress.elapsed_seconds)
        minutes, seconds = divmod(elapsed, 60)
        parts = [progress.message, f"{minutes:02d}:{seconds:02d}"]
        if progress.stage:
            parts.append(progress.stage)
        if progress.eta_seconds is not None:
            eta = int(progress.eta_seconds)
            em, es = divmod(eta, 60)
            parts.append(f"ETA {em:02d}:{es:02d}")
        label = progress.short_label
        if label:
            parts.append(label)
        self._queue.setText("  ·  ".join(parts))

    def _on_movie_finished(self, result) -> None:
        if self._is_generation_for_project():
            return
        if self._channel_name and self._project_folder:
            self.refresh()
        if not self.isVisible():
            self._sync_job_buttons()
            return
        if result.queue_total:
            self._queue.setText(
                f"Movie finished — {result.queue_current}/{result.queue_total}"
            )
        self._show_result(result)
        self._sync_job_buttons()

    def _on_thumbnail_primary_clicked(self) -> None:
        app = self._app()
        if app is None:
            return
        if app.tasks.is_thumbnail_running and self._is_active_job():
            app.tasks.stop_thumbnail()
            self._queue.setText("Stopping thumbnail…")
            return
        self._start_thumbnail()

    def _run_regenerate_thumbnail(self) -> None:
        self._start_thumbnail()

    def _start_thumbnail(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.tasks.is_busy:
            QMessageBox.information(
                self,
                "Atlas Studio",
                "A background job is already running. Use Stop, or wait for it to finish.",
            )
            return
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return

        started = app.tasks.start_thumbnail(
            app.production,
            context,
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            QMessageBox.information(
                self, "Atlas Studio", "Could not start thumbnail generation."
            )
            return
        self._queue.setText("Starting thumbnail…")
        self._result.setText("Generating thumbnail in background…")
        self._sync_job_buttons()

    def _on_thumbnail_progress(self, progress: ThumbnailQueueProgress) -> None:
        if self._is_generation_for_project() or not self._is_active_job():
            return
        elapsed = int(progress.elapsed_seconds)
        minutes, seconds = divmod(elapsed, 60)
        parts = [progress.message, f"{minutes:02d}:{seconds:02d}"]
        if progress.stage:
            parts.append(progress.stage)
        self._queue.setText("  ·  ".join(parts))

    def _on_thumbnail_finished(self, result) -> None:
        if self._is_generation_for_project():
            return
        if self._channel_name and self._project_folder:
            self.refresh()
        if not self.isVisible():
            self._sync_job_buttons()
            return
        self._show_result(result)
        self._sync_job_buttons()

    def _is_active_job(self) -> bool:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return False
        return app.tasks.is_job_for(self._channel_name, self._project_folder)

    def _sync_job_buttons(self, *_args) -> None:
        app = self._app()
        one_click = bool(
            app
            and app.generation.is_running
            and self._is_generation_for_project()
        )
        busy = bool(app and (app.tasks.is_busy or app.generation.is_running))
        mine = self._is_active_job()
        images_mine = bool(app and app.tasks.is_images_running and mine and not one_click)
        voice_mine = bool(app and app.tasks.is_voice_running and mine and not one_click)
        movie_mine = bool(app and app.tasks.is_movie_running and mine and not one_click)
        thumbnail_mine = bool(
            app and app.tasks.is_thumbnail_running and mine and not one_click
        )

        self._generate_everything.setEnabled(not busy)
        self._cancel_production.setEnabled(one_click)

        if one_click:
            self._generate.setEnabled(False)
            self._regen_script.setEnabled(False)
            self._regen_sheet.setEnabled(False)
            self._generate_images.setText("Generate Images")
            self._generate_images.setEnabled(False)
            self._regen_images.setEnabled(False)
            self._generate_voice.setText("Generate Voice")
            self._generate_voice.setEnabled(False)
            self._regen_voice.setEnabled(False)
            self._generate_movie.setText("Generate Movie")
            self._generate_movie.setEnabled(False)
            self._regen_movie.setEnabled(False)
            self._generate_thumbnail.setText("Generate Thumbnail")
            self._generate_thumbnail.setEnabled(False)
            self._regen_thumbnail.setEnabled(False)
            return

        if images_mine:
            self._generate_images.setText("Stop")
            self._generate_images.setEnabled(True)
            self._regen_images.setEnabled(False)
        else:
            self._generate_images.setText("Generate Images")
            self._generate_images.setEnabled(not busy)
            self._regen_images.setEnabled(not busy)

        if voice_mine:
            self._generate_voice.setText("Stop")
            self._generate_voice.setEnabled(True)
            self._regen_voice.setEnabled(False)
        else:
            self._generate_voice.setText("Generate Voice")
            self._generate_voice.setEnabled(not busy)
            self._regen_voice.setEnabled(not busy)

        if movie_mine:
            self._generate_movie.setText("Stop")
            self._generate_movie.setEnabled(True)
            self._regen_movie.setEnabled(False)
        else:
            self._generate_movie.setText("Generate Movie")
            self._generate_movie.setEnabled(not busy)
            self._regen_movie.setEnabled(not busy)

        if thumbnail_mine:
            self._generate_thumbnail.setText("Stop")
            self._generate_thumbnail.setEnabled(True)
            self._regen_thumbnail.setEnabled(False)
        else:
            self._generate_thumbnail.setText("Generate Thumbnail")
            self._generate_thumbnail.setEnabled(not busy)
            self._regen_thumbnail.setEnabled(not busy)

        self._generate.setEnabled(not busy)
        self._regen_script.setEnabled(not busy)
        self._regen_sheet.setEnabled(not busy)

    def _refresh_voice_panel(self) -> None:
        path = self._resolve_voice_path()
        if path is None:
            self._voice_info.setText("No voice file yet")
            self._voice_player.set_source(None)
            return
        info = voice_file_info(path, duration_ms=self._voice_player.duration_ms or None)
        if info is None:
            self._voice_info.setText("No voice file yet")
            self._voice_player.set_source(None)
            return
        self._voice_info.setText(f"✔ Voice  ·  {info.summary}")
        self._voice_player.set_source(path)

    def _refresh_channel_narrator(self) -> None:
        """Show the channel's preferred narrator when a project is opened."""
        from app.channels.voice_preferences import ChannelVoicePreferences

        app = self._app()
        if app is None or not self._channel_name:
            self._voice_narrator.setText("")
            return
        try:
            channel = app.channels.get_channel(self._channel_name)
            prefs = ChannelVoicePreferences.from_mapping(channel.voice)
        except Exception:  # noqa: BLE001
            self._voice_narrator.setText("")
            return
        if not prefs.voice_id and not prefs.voice_name:
            self._voice_narrator.setText("Narrator: using app default voice settings")
            return
        parts = [prefs.voice_name or prefs.voice_id]
        if prefs.gender:
            parts.append(prefs.gender)
        if prefs.language:
            parts.append(prefs.language)
        if prefs.style_tags:
            parts.append(prefs.style_tags[0])
        self._voice_narrator.setText("Narrator: " + " · ".join(parts))

    def _on_voice_duration(self, duration_ms: int) -> None:
        path = self._resolve_voice_path()
        if path is None:
            return
        info = voice_file_info(path, duration_ms=duration_ms)
        if info is not None:
            self._voice_info.setText(f"✔ Voice  ·  {info.summary}")

    def _resolve_voice_path(self) -> Path | None:
        try:
            context = self._context()
        except Exception:  # noqa: BLE001
            return None
        return ArtifactResolver(context.project_dir).find(ArtifactKind.VOICE)

    def _open_images_folder(self) -> None:
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        folder = resolve_images_dir(context.project_dir)
        self._open_path(folder)

    def _open_voice_folder(self) -> None:
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        folder = resolve_voice_dir(context.project_dir)
        self._open_path(folder)

    def _open_movie_folder(self) -> None:
        """Open final output folder (future: separate Open Working Files)."""
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._open_path(resolve_youtube_dir(context.project_dir))

    def _open_movie_video(self) -> None:
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        path = ArtifactResolver(context.project_dir).find(ArtifactKind.YOUTUBE_EXPORT)
        if path is None:
            path = final_video_path(context.project_dir)
            if not path.is_file():
                QMessageBox.information(
                    self,
                    "Atlas Studio",
                    "No final video yet. Generate Movie first.",
                )
                return
        self._open_path(path)

    def _open_thumbnail_folder(self) -> None:
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._open_path(resolve_thumbnail_dir(context.project_dir))

    def _open_thumbnail_file(self) -> None:
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        path = ArtifactResolver(context.project_dir).find(ArtifactKind.THUMBNAIL)
        if path is None:
            path = thumbnail_path(context.project_dir)
            if not path.is_file():
                QMessageBox.information(
                    self,
                    "Atlas Studio",
                    "No thumbnail yet. Generate Thumbnail first.",
                )
                return
        self._open_path(path)

    def _show_result(self, result) -> None:
        app = self._app()
        detail = result.message
        if result.errors:
            detail = f"{detail} — {'; '.join(result.errors)}"
        self._result.setText(
            f"{result.outcome.value}: {detail} ({result.execution_time_ms:.0f} ms)"
        )
        if app is None:
            return
        # Background job completions notify from MainWindow.
        lowered = result.message.casefold()
        background = (
            "image" in lowered
            or "voice" in lowered
            or "exported" in lowered
            or "scene" in lowered
            or "thumbnail" in lowered
        )
        if result.outcome == PipelineOutcome.SUCCESS:
            if not background:
                app.show_notification("Production Updated", result.message)
        elif result.outcome == PipelineOutcome.WARNING:
            if not background:
                app.show_notification("Production Warning", result.message)
        elif result.outcome == PipelineOutcome.FAILED:
            if not app.tasks.is_busy:
                app.show_notification("Production Failed", result.message)
                QMessageBox.warning(self, "Atlas Studio", result.message)

    def _open_artifact(self, kind: ArtifactKind) -> None:
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        path = ArtifactResolver(context.project_dir).open_path(kind)
        if path is None:
            label = "Script" if kind == ArtifactKind.SCRIPT else "Production Sheet"
            QMessageBox.information(
                self,
                "Atlas Studio",
                f"No {label} artifact found yet. Run Generate Production first.",
            )
            return
        self._open_path(path)

    def _open_path(self, path: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))

    def _clear_progress(self) -> None:
        while self._progress_layout.count():
            item = self._progress_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
