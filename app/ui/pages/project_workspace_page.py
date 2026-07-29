"""Project workspace — production progress and Generate Production."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.pipelines.artifacts import (
    PRODUCTION_SHEET_FILENAME,
    SCRIPT_FILENAME,
    SCRIPT_FOLDER,
)
from app.pipelines.context import ChannelDefaults
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

        topic_label = QLabel("Topic")
        topic_label.setObjectName("SectionLabel")

        self._topic = QLineEdit()
        self._topic.setPlaceholderText("Enter the topic for this production")

        self._generate = QPushButton("Generate Production")
        self._generate.setObjectName("PrimaryButton")
        self._generate.clicked.connect(self._generate_production)

        open_script = QPushButton("Open Script")
        open_script.clicked.connect(lambda: self._open_artifact(SCRIPT_FILENAME))

        open_sheet = QPushButton("Open Production Sheet")
        open_sheet.clicked.connect(lambda: self._open_artifact(PRODUCTION_SHEET_FILENAME))

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
        layout.addWidget(topic_label)
        layout.addWidget(self._topic)
        layout.addLayout(primary_row)
        layout.addLayout(secondary_row)
        layout.addLayout(regen_row)
        layout.addWidget(self._result)
        layout.addSpacing(14)
        layout.addWidget(progress_label)
        layout.addWidget(scroll, stretch=1)

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

        if not self._topic.text().strip():
            self._topic.setText(project.idea or "")

        self._clear_progress()
        for step in progress.steps:
            self._progress_layout.addWidget(ProgressRow(step.label, step.state))
        self._progress_layout.addStretch()

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
        topic = self._topic.text().strip()
        if not topic:
            QMessageBox.warning(self, "Atlas Studio", "Enter a topic first.")
            return
        self._generate.setEnabled(False)
        self._result.setText("Generating production…")
        app.processEvents()
        try:
            app.projects.update_idea(self._channel_name, self._project_folder, topic)
            result = app.production.generate_production(self._context(), topic=topic)
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
        topic = self._topic.text().strip()
        try:
            if topic and self._channel_name and self._project_folder:
                app.projects.update_idea(self._channel_name, self._project_folder, topic)
            result = app.production.regenerate_script(self._context(), topic=topic or None)
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
        if result.outcome == PipelineOutcome.SUCCESS:
            app.show_notification("Production Updated", result.message)
        elif result.outcome == PipelineOutcome.FAILED:
            app.show_notification("Production Failed", result.message)
            QMessageBox.warning(self, "Atlas Studio", result.message)

    def _open_artifact(self, filename: str) -> None:
        try:
            context = self._context()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        path = context.folder(SCRIPT_FOLDER) / filename
        if not path.is_file():
            QMessageBox.information(
                self,
                "Atlas Studio",
                f"{filename} does not exist yet. Run Generate Production first.",
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
