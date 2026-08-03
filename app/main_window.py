"""Main application window shell."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.diagnostics.startup_profiler import StartupProfiler
from app.pipelines.results import PipelineOutcome
from app.providers.backend_status import BackendStatus
from app.ui.branding.identity import WINDOW_TITLE
from app.ui.motion.fades import fade_widget
from app.ui.notifications.notification_host import NotificationHost
from app.ui.sidebar import Sidebar


# Sidebar-visible production pages only.
_NAV_KEYS = frozenset(
    {
        "dashboard",
        "channels",
        "projects",
        "settings",
    }
)

# Hidden / secondary pages still constructable (not in sidebar).
# TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
_HIDDEN_PAGE_KEYS = frozenset(
    {
        "project_workspace",
        "channel_dashboard",
        "channel_settings",
        "channel_studio",
        "ai_workflow",  # Creative Brief — use via workflow later; not a toolbox entry
        "thumbnail_review",
        "design_review",
        "ai_providers",  # App-level connections only (Settings Advanced)
    }
)


class MainWindow(QMainWindow):
    """Shell hosting sidebar navigation and pages."""

    def __init__(self) -> None:
        super().__init__()
        profiler = StartupProfiler.instance()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1200, 760)
        self.setMinimumSize(900, 600)
        self._forge_exit_handled = False

        root = QWidget()
        self.setCentralWidget(root)

        profiler.begin("sidebar_construct")
        self._sidebar = Sidebar()
        profiler.end("sidebar_construct")

        self._pages = QStackedWidget()
        self._page_index: dict[str, int] = {}
        self._page_widgets: dict[str, QWidget] = {}

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._pages, stretch=1)

        self._notifications = NotificationHost(root)
        app = AtlasApplication.instance()
        if isinstance(app, AtlasApplication):
            app.set_notification_host(self._notifications)

        # Bottom status bar removed — live status lives in the sidebar Status card.
        unused_bar = QStatusBar()
        unused_bar.setVisible(False)
        unused_bar.setMaximumHeight(0)
        self.setStatusBar(unused_bar)

        if isinstance(app, AtlasApplication):
            app.tasks.status_changed.connect(self._on_global_status)
            app.tasks.image_progress.connect(self._on_image_progress)
            app.tasks.voice_progress.connect(self._on_voice_progress)
            app.tasks.movie_progress.connect(self._on_movie_progress)
            app.tasks.thumbnail_progress.connect(self._on_thumbnail_progress)
            app.tasks.shorts_progress.connect(self._on_shorts_progress)
            app.tasks.image_finished.connect(self._on_image_finished)
            app.tasks.voice_finished.connect(self._on_voice_finished)
            app.tasks.movie_finished.connect(self._on_movie_finished)
            app.tasks.thumbnail_finished.connect(self._on_thumbnail_finished)
            app.tasks.shorts_finished.connect(self._on_shorts_finished)
            app.generation.status_updated.connect(self._on_generation_status)
            app.generation.running_changed.connect(self._on_generation_running)
            app.generation.finished.connect(self._on_generation_finished)
            self._on_global_status(app.tasks.status)
            app.forge_status.status_changed.connect(self._on_forge_status)
            app.forge_status.message_changed.connect(self._on_forge_message)
            self._sync_forge_indicator()

        self._sidebar.page_requested.connect(self._show_page)
        self._sidebar.about_requested.connect(self._open_about)
        self._sidebar.forge_settings_requested.connect(self._open_forge_settings)
        self._sidebar.forge_action_requested.connect(self._on_forge_action)

        # Eagerly create only the landing page; other pages load on first visit.
        with profiler.stage("dashboard_creation"):
            self._ensure_page("dashboard")
            self._show_page("dashboard")

    def _page_factory(self, key: str) -> Callable[[], QWidget]:
        def load(module_path: str, attr: str) -> Callable[[], QWidget]:
            def factory() -> QWidget:
                from importlib import import_module

                module = import_module(module_path)
                cls = getattr(module, attr)
                return cls()

            return factory

        # Page modules are kept; sidebar only exposes production keys in _NAV_KEYS.
        # TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
        factories: dict[str, Callable[[], QWidget]] = {
            "dashboard": load("app.ui.pages.dashboard_page", "DashboardPage"),
            "channels": load("app.ui.pages.channels_page", "ChannelsPage"),
            "channel_dashboard": load(
                "app.ui.pages.channel_dashboard_page", "ChannelDashboardPage"
            ),
            "channel_settings": load(
                "app.ui.pages.channel_settings_page", "ChannelSettingsPage"
            ),
            "channel_studio": load("app.ui.pages.channel_studio", "ChannelStudioPage"),
            "projects": load("app.ui.pages.projects_page", "ProjectsPage"),
            "project_workspace": load(
                "app.ui.pages.project_workspace_page", "ProjectWorkspacePage"
            ),
            # Disconnected from sidebar — Settings embeds AIProvidersPage.
            "ai_workflow": load("app.ui.pages.ai_workflow_page", "AIWorkflowPage"),
            "thumbnail_review": load(
                "app.ui.pages.thumbnail_review_page", "ThumbnailReviewPage"
            ),
            "design_review": load("app.ui.pages.design_review_page", "DesignReviewPage"),
            "ai_providers": load("app.ui.pages.ai_providers_page", "AIProvidersPage"),
            "settings": load("app.ui.pages.settings_page", "SettingsPage"),
        }
        factory = factories.get(key)
        if factory is None:
            raise KeyError(f"Unknown page key: {key}")
        if key not in _NAV_KEYS and key not in _HIDDEN_PAGE_KEYS:
            raise KeyError(f"Page key not registered for V3 UI: {key}")
        return factory

    def _ensure_page(self, key: str) -> QWidget:
        existing = self._page_widgets.get(key)
        if existing is not None:
            return existing
        widget = self._page_factory(key)()
        self._wire_page(key, widget)
        index = self._pages.addWidget(widget)
        self._page_index[key] = index
        self._page_widgets[key] = widget
        return widget

    def _wire_page(self, key: str, widget: QWidget) -> None:
        if key == "projects":
            widget.project_open_requested.connect(self._open_workspace)  # type: ignore[attr-defined]
        elif key == "project_workspace":
            widget.back_requested.connect(  # type: ignore[attr-defined]
                lambda: self._show_page("projects")
            )
        elif key == "channels":
            widget.channel_studio_requested.connect(self._open_channel_studio)  # type: ignore[attr-defined]
            widget.channel_dashboard_requested.connect(self._open_channel_dashboard)  # type: ignore[attr-defined]
        elif key == "channel_dashboard":
            widget.back_requested.connect(lambda: self._show_page("channels"))  # type: ignore[attr-defined]
            widget.project_open_requested.connect(self._open_workspace)  # type: ignore[attr-defined]
            widget.channel_settings_requested.connect(self._open_channel_settings)  # type: ignore[attr-defined]
            widget.channel_studio_requested.connect(self._open_channel_studio)  # type: ignore[attr-defined]
            widget.create_project_requested.connect(self._create_project_for_channel)  # type: ignore[attr-defined]
        elif key == "channel_settings":
            widget.back_requested.connect(self._back_to_channel_dashboard)  # type: ignore[attr-defined]
            widget.channel_studio_requested.connect(self._open_channel_studio)  # type: ignore[attr-defined]
        elif key == "channel_studio":
            pass

    def show_startup_timeline(self) -> None:
        """Open the Developer Mode startup timeline (from memory or last log)."""
        from app.ui.dialogs.startup_timeline_dialog import StartupTimelineDialog

        app = AtlasApplication.instance()
        profile = None
        if isinstance(app, AtlasApplication):
            profile = app.startup_profile
        if profile is None:
            profile = StartupProfiler.instance().profile
        StartupTimelineDialog(profile, parent=self).exec()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._confirm_forge_shutdown():
            event.ignore()
            return
        self._forge_exit_handled = True
        super().closeEvent(event)

    def _confirm_forge_shutdown(self) -> bool:
        """Ask whether to close Forge when Atlas started it. Never kill external Forge."""
        if self._forge_exit_handled:
            return True
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return True
        service = app.forge_status
        if not service.started_by_atlas:
            return True

        box = QMessageBox(self)
        box.setWindowTitle("Atlas Studio")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Atlas started Forge for this session.")
        box.setInformativeText("Do you want to close Forge when Atlas exits?")
        close_cb = QCheckBox("Close Forge when Atlas exits")
        close_cb.setChecked(bool(app.config.forge.close_forge_on_exit))
        box.setCheckBox(close_cb)
        box.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Ok)
        if box.exec() != QMessageBox.StandardButton.Ok:
            return False

        should_close = close_cb.isChecked()
        app.config.forge.close_forge_on_exit = should_close
        try:
            app.config.save()
        except OSError:
            pass
        if should_close:
            service.stop_forge()
        else:
            # Keep Forge running; clear ownership so aboutToQuit won't kill it.
            service.release_ownership()
        return True

    def _on_forge_status(self, status: BackendStatus) -> None:
        del status
        self._sync_forge_indicator()

    def _on_forge_message(self, message: str) -> None:
        del message
        self._sync_forge_indicator()

    def _sync_forge_indicator(self) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        service = app.forge_status
        settings = service.settings
        has_folder = bool((settings.launch_path or "").strip())
        self._sidebar.forge_status.set_connection_info(
            host=settings.host,
            port=settings.port,
            can_control_process=service.started_by_atlas,
            has_launch_folder=has_folder,
        )
        self._sidebar.forge_status.set_status(service.status, service.message)

    def _on_forge_action(self, action_id: str) -> None:
        """Route indicator menu actions through ForgeStatusService only."""
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        service = app.forge_status
        action = (action_id or "").strip().casefold()

        if action == "settings":
            self._open_forge_settings()
            return
        if action == "open_webui":
            if not service.open_webui():
                app.show_notification("Forge", "Could not open Forge WebUI.")
            return
        if action == "open_folder":
            if not service.open_forge_folder():
                app.show_notification(
                    "Forge",
                    "Set a Launch Path in Forge Settings to open the folder.",
                )
            return
        if action == "start":
            if not service.start_forge():
                app.show_notification("Forge", service.message or "Could not start Forge.")
            else:
                app.show_notification("Forge", "Starting Forge...")
            self._sync_forge_indicator()
            return
        if action == "stop":
            if not service.stop_forge():
                app.show_notification(
                    "Forge",
                    "Atlas can only stop Forge when it started it this session.",
                )
            else:
                app.show_notification("Forge", "Forge stopped.")
            self._sync_forge_indicator()
            return
        if action == "restart":
            if not service.restart_forge():
                app.show_notification("Forge", service.message or "Could not restart Forge.")
            else:
                app.show_notification("Forge", "Restarting Forge...")
            self._sync_forge_indicator()

    def _open_about(self) -> None:
        page = self._ensure_page("settings")
        open_about = getattr(page, "open_about", None)
        if callable(open_about):
            open_about()
        self._show_page("settings")

    def _open_forge_settings(self) -> None:
        self._show_page("settings")
        page = self._page_widgets.get("settings")
        focus = getattr(page, "focus_forge_section", None) if page else None
        if callable(focus):
            focus()

    def _on_global_status(self, text: str) -> None:
        app = AtlasApplication.instance()
        if isinstance(app, AtlasApplication) and app.generation.is_running:
            return
        self._sidebar.status_card.set_from_status_text(text)

    def _on_generation_status(self, status) -> None:
        self._sidebar.status_card.set_from_generation_status(status)

    def _on_generation_running(self, running: bool) -> None:
        if not running:
            app = AtlasApplication.instance()
            if isinstance(app, AtlasApplication):
                self._on_global_status(app.tasks.status)

    def _on_generation_finished(self, result) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        if result.outcome == PipelineOutcome.SUCCESS:
            app.show_notification("Production Complete", result.message or "Production Completed")
        elif result.outcome == PipelineOutcome.CANCELLED:
            app.show_notification("Production Cancelled", result.message or "Generation Cancelled")
        elif result.outcome == PipelineOutcome.FAILED:
            app.show_notification("Production Failed", result.message)
            self._sidebar.status_card.set_progress(
                task="Failed",
                item=result.message,
                percent=0,
                error=result.message,
            )

    def _one_click_running(self) -> bool:
        app = AtlasApplication.instance()
        return bool(isinstance(app, AtlasApplication) and app.generation.is_running)

    def _on_image_progress(self, progress: ImageQueueProgress) -> None:
        if self._one_click_running():
            return
        item = progress.message.strip() or progress.short_prompt
        self._sidebar.status_card.set_progress(
            task="Generating Images",
            current=progress.current,
            total=progress.total,
            item=item,
            elapsed_seconds=progress.elapsed_seconds,
        )

    def _on_voice_progress(self, progress: VoiceQueueProgress) -> None:
        if self._one_click_running():
            return
        item = progress.message.strip() or progress.short_detail
        indeterminate = progress.total <= 0
        self._sidebar.status_card.set_progress(
            task="Generating Voice",
            current=None if indeterminate else progress.current,
            total=None if indeterminate else progress.total,
            item=item,
            elapsed_seconds=progress.elapsed_seconds,
            indeterminate=indeterminate,
        )

    def _on_movie_progress(self, progress: MovieQueueProgress) -> None:
        if self._one_click_running():
            return
        item = progress.short_label or progress.message
        self._sidebar.status_card.set_progress(
            task="Generating Movie",
            current=progress.current,
            total=progress.total,
            item=item,
            elapsed_seconds=progress.elapsed_seconds,
            eta_seconds=progress.eta_seconds,
        )

    def _on_thumbnail_progress(self, progress: ThumbnailQueueProgress) -> None:
        if self._one_click_running():
            return
        self._sidebar.status_card.set_progress(
            task="Generating Thumbnail",
            item=progress.message or progress.stage,
            elapsed_seconds=progress.elapsed_seconds,
            indeterminate=True,
        )

    def _on_shorts_progress(self, progress) -> None:
        if self._one_click_running():
            return
        item = progress.message
        if progress.total > 0 and progress.current > 0:
            item = f"Short {progress.current} / {progress.total}"
        self._sidebar.status_card.set_progress(
            task="Creating Shorts",
            current=progress.current if progress.total else None,
            total=progress.total if progress.total else None,
            item=item,
            elapsed_seconds=progress.elapsed_seconds,
            indeterminate=progress.total <= 0,
        )

    def _on_image_finished(self, result) -> None:
        if self._one_click_running():
            return
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
        if self._one_click_running():
            return
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
        if self._one_click_running():
            return
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

    def _on_thumbnail_finished(self, result) -> None:
        if self._one_click_running():
            return
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        if result.outcome == PipelineOutcome.SUCCESS:
            app.show_notification("Thumbnail Complete", result.message)
        elif result.outcome == PipelineOutcome.WARNING:
            app.show_notification("Thumbnail Warning", result.message)
        elif result.outcome == PipelineOutcome.CANCELLED:
            app.show_notification("Thumbnail Cancelled", result.message or "Cancelled")
        elif result.outcome == PipelineOutcome.FAILED:
            app.show_notification("Thumbnail Failed", result.message)

    def _on_shorts_finished(self, result) -> None:
        if self._one_click_running():
            return
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        if result.outcome == PipelineOutcome.SUCCESS:
            app.show_notification("Shorts Complete", result.message)
        elif result.outcome == PipelineOutcome.WARNING:
            app.show_notification("Shorts Warning", result.message)
        elif result.outcome == PipelineOutcome.CANCELLED:
            app.show_notification("Shorts Cancelled", result.message or "Cancelled")
        elif result.outcome == PipelineOutcome.FAILED:
            app.show_notification("Shorts Failed", result.message)

    def _show_page(self, key: str) -> None:
        try:
            self._ensure_page(key)
        except KeyError:
            return
        index = self._page_index.get(key)
        if index is not None:
            self._pages.setCurrentIndex(index)
            current = self._pages.currentWidget()
            if current is not None:
                fade_widget(current, start=0.92, end=1.0, duration_ms=120)
            if key == "project_workspace":
                nav_key = "projects"
            elif key in {
                "channel_studio",
                "channel_dashboard",
                "channel_settings",
            }:
                nav_key = "channels"
            elif key in {"ai_providers", "ai_workflow"}:
                nav_key = "settings"
            else:
                nav_key = key
            if nav_key in _NAV_KEYS:
                self._sidebar.set_active(nav_key)
        self._notifications.raise_()

    def _open_workspace(self, channel_name: str, project_folder: str) -> None:
        workspace = self._ensure_page("project_workspace")
        load = getattr(workspace, "load_project", None)
        if callable(load):
            load(channel_name, project_folder)
        self._show_page("project_workspace")

    def _open_channel_studio(self, folder_name: str) -> None:
        self._show_page("channel_studio")
        studio = self._page_widgets.get("channel_studio")
        load = getattr(studio, "load_channel", None) if studio else None
        if callable(load):
            load(folder_name)

    def _open_channel_dashboard(self, folder_name: str) -> None:
        page = self._ensure_page("channel_dashboard")
        load = getattr(page, "load_channel", None)
        if callable(load):
            load(folder_name)
        self._show_page("channel_dashboard")

    def _open_channel_settings(self, folder_name: str) -> None:
        page = self._ensure_page("channel_settings")
        load = getattr(page, "load_channel", None)
        if callable(load):
            load(folder_name)
        self._show_page("channel_settings")

    def _back_to_channel_dashboard(self) -> None:
        page = self._page_widgets.get("channel_dashboard")
        folder = getattr(page, "_folder", None) if page else None
        if folder:
            self._open_channel_dashboard(str(folder))
        else:
            self._show_page("channels")

    def _create_project_for_channel(self, folder_name: str) -> None:
        from app.ui.dialogs.create_project_dialog import CreateProjectDialog

        dialog = CreateProjectDialog(folder_name, parent=self)
        if dialog.exec() and dialog.created_folder():
            self._open_workspace(folder_name, dialog.created_folder() or "")

    def current_page_key(self) -> str:
        current = self._pages.currentIndex()
        for key, index in self._page_index.items():
            if index == current:
                return key
        return "dashboard"

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._notifications.setGeometry(
            0, 0, self.centralWidget().width(), self.centralWidget().height()
        )
