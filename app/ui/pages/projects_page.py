"""Projects page — list, create, open, and delete projects for the active channel."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.core.project_root import ProjectRootError, is_project_root_configured
from app.ui.widgets.empty_state import EmptyState


class ProjectsPage(QWidget):
    project_open_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Projects")
        title.setObjectName("PageTitle")

        self._subtitle = QLabel("Select a channel to manage its projects.")
        self._subtitle.setObjectName("PageSubtitle")

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._open_selected)

        self._empty = EmptyState()

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Project title (number assigned automatically)")

        self._idea_input = QLineEdit()
        self._idea_input.setPlaceholderText("Idea (optional)")
        self._idea_input.returnPressed.connect(self._create_project)

        create_button = QPushButton("Create Project")
        create_button.setObjectName("PrimaryButton")
        create_button.clicked.connect(self._create_project)

        open_button = QPushButton("Open")
        open_button.clicked.connect(self._open_selected)

        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self._delete_selected)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)

        create_row = QHBoxLayout()
        create_row.addWidget(self._name_input, stretch=1)
        create_row.addWidget(self._idea_input, stretch=2)
        create_row.addWidget(create_button)

        action_row = QHBoxLayout()
        action_row.addWidget(open_button)
        action_row.addWidget(delete_button)
        action_row.addWidget(refresh_button)
        action_row.addStretch()

        self._status = QLabel("")
        self._status.setObjectName("PageSubtitle")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(self._subtitle)
        layout.addWidget(self._list, stretch=1)
        layout.addWidget(self._empty, stretch=1)
        layout.addLayout(create_row)
        layout.addLayout(action_row)
        layout.addWidget(self._status)
        self._empty.hide()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def _focus_create(self) -> None:
        self._name_input.setFocus()

    def _go_settings(self) -> None:
        window = self.window()
        show = getattr(window, "_show_page", None)
        if callable(show):
            show("settings")

    def _go_channels(self) -> None:
        window = self.window()
        show = getattr(window, "_show_page", None)
        if callable(show):
            show("channels")

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _show_list(self, visible: bool) -> None:
        self._list.setVisible(visible)
        self._empty.setVisible(not visible)

    def refresh(self) -> None:
        app = self._app()
        self._list.clear()
        if app is None:
            self._subtitle.setText("Application is not ready.")
            self._show_list(False)
            return

        if not is_project_root_configured(app.config.project_root):
            self._subtitle.setText("Project Root is not set.")
            self._status.setText("")
            self._empty.configure(
                "No Project Root",
                "Set your YouTube library folder in Settings before managing projects.",
                "Open Settings",
                self._go_settings,
            )
            self._show_list(False)
            return

        channel = app.channels.active_channel_name
        if not channel:
            self._subtitle.setText("No active channel.")
            self._status.setText("")
            self._empty.configure(
                "No Channel selected",
                "Open Channels, select a channel, then return here to create projects.",
                "Open Channels",
                self._go_channels,
            )
            self._show_list(False)
            return

        try:
            projects = app.projects.list_projects(channel)
        except (ProjectRootError, OSError) as exc:
            self._subtitle.setText(str(exc))
            self._status.setText("")
            self._show_list(False)
            return

        self._subtitle.setText(f"Channel: {channel}  ·  {len(projects)} project(s)")
        for project in projects:
            try:
                status = app.projects.lifecycle_status(channel, project.folder_name)
            except (ProjectRootError, OSError, FileNotFoundError):
                status = project.status
            item = QListWidgetItem(f"{project.name}  —  {status}")
            item.setData(Qt.ItemDataRole.UserRole, project.folder_name)
            self._list.addItem(item)

        if not projects:
            self._empty.configure(
                "No Projects yet",
                "Create a project from an idea. Numbers are assigned automatically.",
                "Create Project",
                self._focus_create,
            )
            self._show_list(False)
            self._status.setText("")
            return

        self._show_list(True)
        self._status.setText("Double-click a project to open it.")

    def _selected_folder(self) -> str | None:
        items = self._list.selectedItems()
        if not items:
            return None
        value = items[0].data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def _create_project(self) -> None:
        app = self._app()
        if app is None:
            return
        channel = app.channels.active_channel_name
        if not channel:
            QMessageBox.warning(self, "Atlas Studio", "Select a channel first.")
            return
        name = self._name_input.text().strip()
        idea = self._idea_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Atlas Studio", "Enter a project name.")
            return
        try:
            project = app.projects.create_project(channel, name, idea=idea)
            app.projects.open_project(channel, project.folder_name)
        except (ProjectRootError, ValueError, FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._name_input.clear()
        self._idea_input.clear()
        self.refresh()
        app.show_notification("Project Created", project.folder_name)
        self.project_open_requested.emit(channel, project.folder_name)

    def _open_selected(self) -> None:
        app = self._app()
        if app is None:
            return
        channel = app.channels.active_channel_name
        folder = self._selected_folder()
        if not channel or not folder:
            QMessageBox.warning(self, "Atlas Studio", "Select a project to open.")
            return
        try:
            app.projects.open_project(channel, folder)
        except (ProjectRootError, FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self.project_open_requested.emit(channel, folder)

    def _delete_selected(self) -> None:
        app = self._app()
        if app is None:
            return
        channel = app.channels.active_channel_name
        folder = self._selected_folder()
        if not channel or not folder:
            QMessageBox.warning(self, "Atlas Studio", "Select a project to delete.")
            return
        confirm = QMessageBox.question(
            self,
            "Atlas Studio",
            f'Delete project "{folder}"? This cannot be undone.',
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            app.projects.delete_project(channel, folder)
        except (ProjectRootError, FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self.refresh()
        app.show_notification("Project Deleted", folder)
