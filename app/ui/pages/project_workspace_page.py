"""Project workspace — production progress and Generate Production / Images."""

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
from app.ui.widgets.progress_row import ProgressRow


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
        app.tasks.image_running_changed.connect(self._sync_image_buttons)

    def load_project(self, channel_name: str, project_folder: str) -> None:
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
        self._sync_image_buttons()

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
        if app.tasks.is_images_running and self._is_active_image_job():
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
        if app.tasks.is_images_running:
            QMessageBox.information(
                self,
                "Atlas Studio",
                "An image job is already running. Use Stop, or wait for it to finish.",
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
        self._sync_image_buttons()

    def _on_image_progress(self, progress: ImageQueueProgress) -> None:
        if not self._is_active_image_job():
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
        # Refresh if this project was the job target (even if user navigated away and back).
        app = self._app()
        job = app.tasks.active_image_job if app is not None else None
        # Job cleared after finish — match via result only when page is this project.
        if self._channel_name and self._project_folder:
            self.refresh()
        if not self.isVisible():
            self._sync_image_buttons()
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
        self._sync_image_buttons()

    def _is_active_image_job(self) -> bool:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return False
        return app.tasks.is_job_for(self._channel_name, self._project_folder)

    def _sync_image_buttons(self, *_args) -> None:
        app = self._app()
        running = bool(app and app.tasks.is_images_running)
        mine = self._is_active_image_job()
        if running and mine:
            self._generate_images.setText("Stop")
            self._generate_images.setEnabled(True)
            self._regen_images.setEnabled(False)
        else:
            self._generate_images.setText("Generate Images")
            self._generate_images.setEnabled(not running)
            self._regen_images.setEnabled(not running)

    def _open_images_folder(self) -> None:
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        folder = resolve_images_dir(context.project_dir)
        self._open_path(folder)

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
        # Image completions notify from MainWindow; keep dialogs for text pipelines.
        if result.outcome == PipelineOutcome.SUCCESS:
            if "image" not in result.message.casefold():
                app.show_notification("Production Updated", result.message)
        elif result.outcome == PipelineOutcome.WARNING:
            if "image" not in result.message.casefold():
                app.show_notification("Production Warning", result.message)
        elif result.outcome == PipelineOutcome.FAILED:
            if not app.tasks.is_images_running:
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
