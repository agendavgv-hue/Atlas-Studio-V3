"""Project workspace — production progress only."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
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
        layout.addSpacing(14)
        layout.addWidget(progress_label)
        layout.addWidget(scroll, stretch=1)

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
            self._meta.setText("")
            self._clear_progress()
            return

        self._title.setText(project.name)
        self._meta.setText(f"{project.channel_name} • {project.status}")

        self._clear_progress()
        for step in progress.steps:
            self._progress_layout.addWidget(ProgressRow(step.label, step.state))
        self._progress_layout.addStretch()

    def _clear_progress(self) -> None:
        while self._progress_layout.count():
            item = self._progress_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
