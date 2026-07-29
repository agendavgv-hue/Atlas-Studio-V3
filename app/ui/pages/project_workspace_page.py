"""Project workspace — lifecycle + project intelligence progress."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication


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

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("PageSubtitle")

        progress_label = QLabel("Progress")
        progress_label.setObjectName("PageSubtitle")

        self._progress = QListWidget()
        self._progress.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._progress.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addWidget(self._title)
        layout.addWidget(self._subtitle)
        layout.addSpacing(8)
        layout.addWidget(progress_label)
        layout.addWidget(self._progress, stretch=1)

    def load_project(self, channel_name: str, project_folder: str) -> None:
        self._channel_name = channel_name
        self._project_folder = project_folder
        self.refresh()

    def refresh(self) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        if not self._channel_name or not self._project_folder:
            return
        try:
            project = app.projects.get_project(self._channel_name, self._project_folder)
            progress = app.projects.get_progress(self._channel_name, self._project_folder)
        except (OSError, FileNotFoundError, ValueError):
            self._title.setText("Project not found")
            self._subtitle.setText("")
            self._progress.clear()
            return

        self._title.setText(project.name)
        idea = project.idea or "(no idea yet)"
        self._subtitle.setText(
            f"Channel: {project.channel_name}  ·  Status: {project.status}  ·  Idea: {idea}"
        )

        self._progress.clear()
        for step in progress.steps:
            self._progress.addItem(QListWidgetItem(step.display))
