"""Channel Dashboard — home for one production studio."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.channels.production_profile import ChannelProductionProfile
from app.core.project_root import ProjectRootError
from app.ui.widgets.empty_state import EmptyState


class ChannelDashboardPage(QWidget):
    """Channel-centric home: defaults, recent projects, create, settings."""

    project_open_requested = Signal(str, str)
    channel_settings_requested = Signal(str)
    channel_studio_requested = Signal(str)
    create_project_requested = Signal(str)
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")
        self._folder: str | None = None

        back = QPushButton("← Channels")
        back.setObjectName("SecondaryButton")
        back.clicked.connect(self.back_requested.emit)

        self._title = QLabel("Channel")
        self._title.setObjectName("PageTitle")

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)

        self._defaults = QLabel("")
        self._defaults.setObjectName("PageSubtitle")
        self._defaults.setWordWrap(True)

        self._stats = QLabel("")
        self._stats.setObjectName("PageSubtitle")
        self._stats.setWordWrap(True)

        create = QPushButton("Create New Project")
        create.setObjectName("PrimaryButton")
        create.setMinimumHeight(44)
        create.clicked.connect(self._emit_create)

        settings = QPushButton("Channel Settings")
        settings.setObjectName("SecondaryButton")
        settings.clicked.connect(self._emit_settings)

        studio = QPushButton("Open Channel Studio")
        studio.setObjectName("SecondaryButton")
        studio.clicked.connect(self._emit_studio)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addWidget(create, stretch=1)
        actions.addWidget(settings)
        actions.addWidget(studio)

        recent_label = QLabel("Recent Projects")
        recent_label.setObjectName("SectionLabel")

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._open_selected)
        self._empty = EmptyState()

        open_btn = QPushButton("Open Project")
        open_btn.setObjectName("PrimaryButton")
        open_btn.clicked.connect(self._open_selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 36)
        layout.setSpacing(12)
        layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._title)
        layout.addWidget(self._subtitle)
        layout.addSpacing(8)
        layout.addWidget(self._defaults)
        layout.addWidget(self._stats)
        layout.addLayout(actions)
        layout.addSpacing(12)
        layout.addWidget(recent_label)
        layout.addWidget(self._list, stretch=1)
        layout.addWidget(self._empty, stretch=1)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self._empty.hide()

    def load_channel(self, folder_name: str) -> None:
        self._folder = folder_name
        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._folder:
            self.refresh()

    def refresh(self) -> None:
        app = self._app()
        if app is None or not self._folder:
            return
        try:
            channel = app.channels.select_channel(self._folder)
            profile = ChannelProductionProfile.from_channel(channel)
            projects = app.projects.list_projects(channel.folder_name)
        except (ProjectRootError, OSError, FileNotFoundError, ValueError) as exc:
            self._title.setText("Channel")
            self._subtitle.setText(str(exc))
            return

        self._title.setText(channel.name)
        self._subtitle.setText(
            channel.description or "Your production studio for this YouTube channel."
        )
        self._defaults.setText(
            "Defaults\n" + "\n".join(f"• {line}" for line in profile.summary_lines())
        )

        complete = 0
        in_progress = 0
        for project in projects:
            try:
                status = app.projects.lifecycle_status(
                    channel.folder_name, project.folder_name
                )
            except Exception:  # noqa: BLE001
                status = project.status
            if status == "Ready to Publish":
                complete += 1
            elif status == "In Progress":
                in_progress += 1

        self._stats.setText(
            f"Projects: {len(projects)}  ·  In progress: {in_progress}  ·  "
            f"Ready: {complete}\n"
            f"Storage: channel library under Project Root / {channel.folder_name}"
        )

        self._list.clear()
        if not projects:
            self._empty.configure(
                "No projects yet",
                "Create a project — it inherits this channel’s voice, AI, and style.",
                "Create New Project",
                self._emit_create,
            )
            self._list.hide()
            self._empty.show()
            return

        self._empty.hide()
        self._list.show()
        for project in projects[:20]:
            try:
                progress = app.projects.get_progress(
                    channel.folder_name, project.folder_name
                )
                status = app.projects.lifecycle_status(
                    channel.folder_name, project.folder_name
                )
                detail = f"{progress.percent_complete}%  ·  {status}"
            except Exception:  # noqa: BLE001
                detail = project.status
            item = QListWidgetItem(f"{project.name}\n{detail}")
            item.setData(Qt.ItemDataRole.UserRole, project.folder_name)
            self._list.addItem(item)

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _emit_create(self) -> None:
        if self._folder:
            self.create_project_requested.emit(self._folder)

    def _emit_settings(self) -> None:
        if self._folder:
            self.channel_settings_requested.emit(self._folder)

    def _emit_studio(self) -> None:
        if self._folder:
            self.channel_studio_requested.emit(self._folder)

    def _open_selected(self) -> None:
        if not self._folder:
            return
        items = self._list.selectedItems()
        if not items:
            QMessageBox.information(self, "Atlas Studio", "Select a project to open.")
            return
        folder = str(items[0].data(Qt.ItemDataRole.UserRole) or "")
        if folder:
            self.project_open_requested.emit(self._folder, folder)
