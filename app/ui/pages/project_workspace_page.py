"""Project workspace — production progress and Generate Production / Images / Voice."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
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
from app.pipelines.voice_naming import resolve_mp3_dir
from app.pipelines.voice_progress import VoiceQueueProgress
from app.render.naming import final_video_path, resolve_youtube_dir
from app.render.progress import MovieQueueProgress
from app.ui.widgets.progress_row import ProgressRow
from app.ui.widgets.voice_player import VoicePlayer


class ProjectWorkspacePage(QWidget):
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")
        self._channel_name: str | None = None
        self._project_folder: str | None = None

        back_button = QPushButton("← Back to Projects")
        back_button.clicked.connect(self.back_requested.emit)

        top = QHBoxLayout()
        top.addWidget(back_button)
        top.addStretch()

        self._title = QLabel("Project")
        self._title.setObjectName("PageTitle")

        self._meta = QLabel("")
        self._meta.setObjectName("PageSubtitle")

        self._generate = QPushButton("Generate Production")
        self._generate.setObjectName("PrimaryButton")
        self._generate.clicked.connect(self._generate_production)

        open_script = QPushButton("Open Script")
        open_script.clicked.connect(lambda: self._open_artifact(ArtifactKind.SCRIPT))

        open_sheet = QPushButton("Open Production Sheet")
        open_sheet.clicked.connect(
            lambda: self._open_artifact(ArtifactKind.PRODUCTION_SHEET)
        )

        regen_script = QPushButton("Regenerate Script")
        regen_script.setObjectName("SecondaryButton")
        regen_script.clicked.connect(self._regenerate_script)

        regen_sheet = QPushButton("Regenerate Production Sheet")
        regen_sheet.setObjectName("SecondaryButton")
        regen_sheet.clicked.connect(self._regenerate_sheet)

        primary_row = QHBoxLayout()
        primary_row.addWidget(self._generate)
        primary_row.addStretch()

        secondary_row = QHBoxLayout()
        secondary_row.addWidget(open_script)
        secondary_row.addWidget(open_sheet)
        secondary_row.addStretch()

        regen_row = QHBoxLayout()
        regen_row.addWidget(regen_script)
        regen_row.addWidget(regen_sheet)
        regen_row.addStretch()

        images_label = QLabel("Images")
        images_label.setObjectName("SectionLabel")

        self._generate_images = QPushButton("Generate Images")
        self._generate_images.setObjectName("PrimaryButton")
        self._generate_images.clicked.connect(self._on_images_primary_clicked)

        open_images = QPushButton("Open Folder")
        open_images.clicked.connect(self._open_images_folder)

        self._regen_images = QPushButton("Regenerate Images")
        self._regen_images.setObjectName("SecondaryButton")
        self._regen_images.clicked.connect(self._run_regenerate_images)

        images_primary = QHBoxLayout()
        images_primary.addWidget(self._generate_images)
        images_primary.addStretch()

        images_secondary = QHBoxLayout()
        images_secondary.addWidget(open_images)
        images_secondary.addWidget(self._regen_images)
        images_secondary.addStretch()

        voice_label = QLabel("Voice")
        voice_label.setObjectName("SectionLabel")

        self._voice_info = QLabel("No voice file yet")
        self._voice_info.setObjectName("PageSubtitle")
        self._voice_info.setWordWrap(True)

        self._generate_voice = QPushButton("Generate Voice")
        self._generate_voice.setObjectName("PrimaryButton")
        self._generate_voice.clicked.connect(self._on_voice_primary_clicked)

        open_voice = QPushButton("Open Folder")
        open_voice.clicked.connect(self._open_voice_folder)

        self._regen_voice = QPushButton("Regenerate Voice")
        self._regen_voice.setObjectName("SecondaryButton")
        self._regen_voice.clicked.connect(self._run_regenerate_voice)

        voice_primary = QHBoxLayout()
        voice_primary.addWidget(self._generate_voice)
        voice_primary.addStretch()

        voice_secondary = QHBoxLayout()
        voice_secondary.addWidget(open_voice)
        voice_secondary.addWidget(self._regen_voice)
        voice_secondary.addStretch()

        self._voice_player = VoicePlayer()
        self._voice_player.duration_ready.connect(self._on_voice_duration)

        movie_label = QLabel("Movie")
        movie_label.setObjectName("SectionLabel")

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

        movie_primary = QHBoxLayout()
        movie_primary.addWidget(self._generate_movie)
        movie_primary.addStretch()

        movie_secondary = QHBoxLayout()
        movie_secondary.addWidget(open_movie)
        movie_secondary.addWidget(open_video)
        movie_secondary.addWidget(self._regen_movie)
        movie_secondary.addStretch()

        self._queue = QLabel("")
        self._queue.setObjectName("PageSubtitle")
        self._queue.setWordWrap(True)

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

        self._result = QLabel("")
        self._result.setObjectName("PageSubtitle")
        self._result.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(self._title)
        layout.addWidget(self._meta)
        layout.addSpacing(8)
        layout.addLayout(primary_row)
        layout.addLayout(secondary_row)
        layout.addLayout(regen_row)
        layout.addSpacing(12)
        layout.addWidget(images_label)
        layout.addLayout(images_primary)
        layout.addLayout(images_secondary)
        layout.addSpacing(12)
        layout.addWidget(voice_label)
        layout.addWidget(self._voice_info)
        layout.addLayout(voice_primary)
        layout.addLayout(voice_secondary)
        layout.addWidget(self._voice_player)
        layout.addSpacing(12)
        layout.addWidget(movie_label)
        layout.addLayout(movie_primary)
        layout.addLayout(movie_secondary)
        layout.addWidget(self._queue)
        layout.addWidget(self._result)
        layout.addSpacing(14)
        layout.addWidget(progress_label)
        layout.addWidget(scroll, stretch=1)

        self._connect_tasks()

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
        if not self._is_active_job():
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
        if not self._is_active_job():
            return
        elapsed = int(progress.elapsed_seconds)
        minutes, seconds = divmod(elapsed, 60)
        parts = [progress.message, f"{minutes:02d}:{seconds:02d}"]
        detail = progress.short_detail
        if detail:
            parts.append(detail)
        self._queue.setText("  ·  ".join(parts))

    def _on_voice_finished(self, result) -> None:
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
        if not self._is_active_job():
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

    def _is_active_job(self) -> bool:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return False
        return app.tasks.is_job_for(self._channel_name, self._project_folder)

    def _sync_job_buttons(self, *_args) -> None:
        app = self._app()
        busy = bool(app and app.tasks.is_busy)
        mine = self._is_active_job()
        images_mine = bool(app and app.tasks.is_images_running and mine)
        voice_mine = bool(app and app.tasks.is_voice_running and mine)
        movie_mine = bool(app and app.tasks.is_movie_running and mine)

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
        # Reload player when path changes or media missing.
        self._voice_player.set_source(path)

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
        folder = resolve_mp3_dir(context.project_dir)
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
        # Image/voice completions notify from MainWindow; keep dialogs for text pipelines.
        lowered = result.message.casefold()
        background = (
            "image" in lowered or "voice" in lowered or "exported" in lowered or "scene" in lowered
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
