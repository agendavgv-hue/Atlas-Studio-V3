"""Application bootstrap for Atlas Studio."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from app.channels.channel_service import ChannelService
from app.core.storage import Storage, build_storage
from app.pipelines.engine import ProductionEngine
from app.pipelines.registry import PipelineRegistry
from app.projects.project_service import ProjectService
from app.providers.forge_status import ForgeStatusService
from app.providers.image_registry import ImageProviderRegistry
from app.providers.registry import ProviderRegistry
from app.providers.voice_registry import VoiceProviderRegistry
from app.tasks.task_manager import TaskManager
from app.ui.branding.icons import app_icon
from app.ui.branding.identity import APP_NAME, ORGANIZATION
from app.ui.theme.atlas_theme import apply_theme


class AtlasApplication(QApplication):
    """Owns application lifecycle, theme, storage, channels, projects, and production."""

    storage: Storage
    channels: ChannelService
    projects: ProjectService
    production: ProductionEngine
    tasks: TaskManager
    forge_status: ForgeStatusService

    def __init__(self, argv: list[str], *, auto_bootstrap: bool = True) -> None:
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.setOrganizationName(ORGANIZATION)
        self.setWindowIcon(app_icon())
        self.setStyle("Fusion")
        apply_theme(self)

        self._notification_host = None
        self.tasks = TaskManager(self)
        self.forge_status = ForgeStatusService(parent=self)
        self._bootstrapped = False
        self.aboutToQuit.connect(self._on_about_to_quit)
        if auto_bootstrap:
            self.bootstrap()

    def bootstrap(self, on_step: Callable[[str], None] | None = None) -> None:
        """Initialize core services. Safe to call once."""
        if self._bootstrapped:
            return

        def step(label: str) -> None:
            if on_step is not None:
                on_step(label)

        step("Storage")
        self.storage = build_storage()
        self.config = self.storage.config

        step("Channels")
        self.channels = ChannelService(self.storage, self.config)

        step("Projects")
        self.projects = ProjectService(self.config)

        step("Project Intelligence")
        from app.projects import project_intelligence as _project_intelligence  # noqa: F401

        step("Production Engine")
        self.rebuild_production_engine()

        step("Forge Status")
        self.forge_status.update_settings(self.config.forge)
        self.forge_status.start()
        self.forge_status.ensure_running_if_configured()

        step("Ready")
        self._bootstrapped = True

    def rebuild_production_engine(self) -> None:
        """Recreate ProductionEngine after AI settings change."""
        registry = (
            self.production.registry
            if getattr(self, "production", None) is not None
            else PipelineRegistry()
        )
        self.production = ProductionEngine(
            self.projects,
            self.config,
            registry=registry,
            provider_registry=ProviderRegistry(self.config),
            image_provider_registry=ImageProviderRegistry(self.config),
            voice_provider_registry=VoiceProviderRegistry(self.config),
        )
        self.tasks.bind_engine(self.production)
        if getattr(self, "forge_status", None) is not None:
            self.forge_status.update_settings(self.config.forge)

    def set_notification_host(self, host) -> None:
        self._notification_host = host

    def show_notification(self, title: str, message: str = "") -> None:
        host = self._notification_host
        if host is not None:
            host.show_toast(title, message)

    def _on_about_to_quit(self) -> None:
        """Stop polling; close Forge only when Atlas owns it and preference is set."""
        service = getattr(self, "forge_status", None)
        if service is None:
            return
        service.stop_polling()
        config = getattr(self, "config", None)
        if (
            config is not None
            and getattr(config.forge, "close_forge_on_exit", False)
            and service.started_by_atlas
        ):
            service.stop_forge()
