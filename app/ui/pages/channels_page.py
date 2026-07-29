"""Channels page — list, create, and select channels."""

from __future__ import annotations

from PySide6.QtCore import Qt
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


class ChannelsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Channels")
        title.setObjectName("PageTitle")

        self._subtitle = QLabel("Select a Project Root in Settings to load channels.")
        self._subtitle.setObjectName("PageSubtitle")

        self._list = QListWidget()
        self._list.setObjectName("ChannelList")
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        self._empty = EmptyState()

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("New channel name")
        self._name_input.returnPressed.connect(self._create_channel)

        create_button = QPushButton("Create Channel")
        create_button.setObjectName("PrimaryButton")
        create_button.clicked.connect(self._create_channel)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)

        create_row = QHBoxLayout()
        create_row.addWidget(self._name_input, stretch=1)
        create_row.addWidget(create_button)
        create_row.addWidget(refresh_button)

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
                "Choose your YouTube library folder in Settings to discover channels.",
                "Open Settings",
                self._go_settings,
            )
            self._show_list(False)
            return

        try:
            channels = app.channels.list_channels()
        except ProjectRootError as exc:
            self._subtitle.setText(str(exc))
            self._status.setText("")
            self._show_list(False)
            return

        self._subtitle.setText(
            f"Project Root: {app.config.project_root}  ·  {len(channels)} channel(s)"
        )
        active = app.channels.active_channel_name
        for channel in channels:
            item = QListWidgetItem(channel.name)
            item.setData(Qt.ItemDataRole.UserRole, channel.folder_name)
            self._list.addItem(item)
            if active and channel.folder_name == active:
                item.setSelected(True)

        if not channels:
            self._empty.configure(
                "No Channels yet",
                "Create a channel or add a folder inside your Project Root.",
                "Create Channel",
                self._focus_create,
            )
            self._show_list(False)
            self._status.setText("")
            return

        self._show_list(True)
        if active:
            self._status.setText(f"Active channel: {active}")
        else:
            self._status.setText("Select a channel to make it active.")

    def _create_channel(self) -> None:
        app = self._app()
        if app is None:
            return
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Atlas Studio", "Enter a channel name.")
            return
        try:
            channel = app.channels.create_channel(name)
            app.channels.select_channel(channel.folder_name)
        except (ProjectRootError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._name_input.clear()
        self.refresh()
        app.show_notification("Channel Created", channel.name)

    def _on_selection_changed(self) -> None:
        app = self._app()
        if app is None:
            return
        items = self._list.selectedItems()
        if not items:
            return
        folder_name = items[0].data(Qt.ItemDataRole.UserRole)
        if not folder_name:
            return
        try:
            app.channels.select_channel(str(folder_name))
        except (ProjectRootError, FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._status.setText(f"Active channel: {folder_name}")
