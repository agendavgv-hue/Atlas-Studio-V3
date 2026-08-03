"""Minimal project create dialog — channel supplies everything else."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.atlas_application import AtlasApplication
from app.channels.production_profile import ChannelProductionProfile
from app.core.project_root import ProjectRootError


class CreateProjectDialog(QDialog):
    def __init__(self, channel_folder: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(420)
        self._channel_folder = channel_folder
        self._created_folder: str | None = None

        title = QLabel("Create project")
        title.setObjectName("PageTitle")
        hint = QLabel(
            f"Channel: {channel_folder}\n"
            "Voice, AI, image style, and export defaults come from the channel."
        )
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Project name")
        self._topic = QLineEdit()
        self._topic.setPlaceholderText("Topic / idea")

        form = QFormLayout()
        form.addRow("Name", self._name)
        form.addRow("Topic", self._topic)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create")
        buttons.accepted.connect(self._create)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def created_folder(self) -> str | None:
        return self._created_folder

    def _create(self) -> None:
        name = self._name.text().strip()
        topic = self._topic.text().strip()
        if not name:
            QMessageBox.warning(self, "New Project", "Enter a project name.")
            return
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        try:
            channel = app.channels.get_channel(self._channel_folder)
            snapshot = ChannelProductionProfile.from_channel(channel).to_dict()
            project = app.projects.create_project(
                self._channel_folder,
                name,
                idea=topic,
                channel_snapshot=snapshot,
            )
            app.projects.open_project(self._channel_folder, project.folder_name)
        except (ProjectRootError, ValueError, FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "New Project", str(exc))
            return
        self._created_folder = project.folder_name
        app.show_notification("Project Created", project.folder_name)
        self.accept()
