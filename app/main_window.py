"""Main application window shell."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QStatusBar, QWidget

from app.atlas_application import AtlasApplication
from app.pipelines.results import PipelineOutcome
from app.ui.branding.identity import WINDOW_TITLE
from app.ui.motion.fades import fade_widget
from app.ui.notifications.notification_host import NotificationHost
from app.ui.pages import ChannelsPage, DashboardPage, ProjectsPage, SettingsPage
from app.ui.pages.project_workspace_page import ProjectWorkspacePage
from app.ui.sidebar import Sidebar


class MainWindow(QMainWindow):
    """Shell hosting sidebar navigation and pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1200, 760)
        self.setMinimumSize(900, 600)

        root = QWidget()
        self.setCentralWidget(root)

        self._sidebar = Sidebar()
        self._pages = QStackedWidget()

        self._projects_page = ProjectsPage()
        self._workspace_page = ProjectWorkspacePage()
        self._settings_page = SettingsPage()

        self._page_index = {
            "dashboard": self._pages.addWidget(DashboardPage()),
            "channels": self._pages.addWidget(ChannelsPage()),
            "projects": self._pages.addWidget(self._projects_page),
            "project_workspace": self._pages.addWidget(self._workspace_page),
            "settings": self._pages.addWidget(self._settings_page),
        }

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._pages, stretch=1)

        self._notifications = NotificationHost(root)
        app = AtlasApplication.instance()
        if isinstance(app, AtlasApplication):
            app.set_notification_host(self._notifications)

        status = QStatusBar()
        self._global_status = QLabel("Ready")
        self._global_status.setObjectName("GlobalStatus")
        status.addWidget(self._global_status, stretch=1)
        self.setStatusBar(status)

        if isinstance(app, AtlasApplication):
            app.tasks.status_changed.connect(self._on_global_status)
            app.tasks.image_finished.connect(self._on_image_finished)
            app.tasks.voice_finished.connect(self._on_voice_finished)
            app.tasks.movie_finished.connect(self._on_movie_finished)
            self._on_global_status(app.tasks.status)

        self._sidebar.page_requested.connect(self._show_page)
        self._sidebar.about_requested.connect(self._settings_page.open_about)
        self._projects_page.project_open_requested.connect(self._open_workspace)
        self._workspace_page.back_requested.connect(lambda: self._show_page("projects"))
        self._show_page("dashboard")

    def _on_global_status(self, text: str) -> None:
        self._global_status.setText(text)
        bar = self.statusBar()
        if bar is not None:
            bar.showMessage("")

    def _on_image_finished(self, result) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        if result.outcome == PipelineOutcome.SUCCESS:
            app.show_notification("Images Complete", result.message)
        elif result.outcome == PipelineOutcome.WARNING:
            app.show_notification("Images Warning", result.message)
        elif result.outcome == PipelineOutcome.CANCELLED:
            app.show_notification("Images Cancelled", result.message or "Cancelled")
        elif result.outcome == PipelineOutcome.FAILED:
            app.show_notification("Images Failed", result.message)

    def _on_voice_finished(self, result) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        if result.outcome == PipelineOutcome.SUCCESS:
            app.show_notification("Voice Complete", result.message)
        elif result.outcome == PipelineOutcome.WARNING:
            app.show_notification("Voice Warning", result.message)
        elif result.outcome == PipelineOutcome.CANCELLED:
            app.show_notification("Voice Cancelled", result.message or "Cancelled")
        elif result.outcome == PipelineOutcome.FAILED:
            app.show_notification("Voice Failed", result.message)

    def _on_movie_finished(self, result) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        if result.outcome == PipelineOutcome.SUCCESS:
            app.show_notification("Movie Complete", result.message)
        elif result.outcome == PipelineOutcome.WARNING:
            app.show_notification("Movie Warning", result.message)
        elif result.outcome == PipelineOutcome.CANCELLED:
            app.show_notification("Movie Cancelled", result.message or "Cancelled")
        elif result.outcome == PipelineOutcome.FAILED:
            app.show_notification("Movie Failed", result.message)

    def _show_page(self, key: str) -> None:
        index = self._page_index.get(key)
        if index is not None:
            self._pages.setCurrentIndex(index)
            current = self._pages.currentWidget()
            if current is not None:
                fade_widget(current, start=0.92, end=1.0, duration_ms=120)
            nav_key = "projects" if key == "project_workspace" else key
            if nav_key in {"dashboard", "channels", "projects", "settings"}:
                self._sidebar.set_active(nav_key)
        self._notifications.raise_()

    def _open_workspace(self, channel_name: str, project_folder: str) -> None:
        self._workspace_page.load_project(channel_name, project_folder)
        self._show_page("project_workspace")

    def current_page_key(self) -> str:
        current = self._pages.currentIndex()
        for key, index in self._page_index.items():
            if index == current:
                return key
        return "dashboard"

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._notifications.setGeometry(0, 0, self.centralWidget().width(), self.centralWidget().height())
