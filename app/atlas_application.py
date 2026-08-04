"""Application bootstrap for Atlas Studio."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.diagnostics.startup_profiler import StartupProfiler
from app.ui.branding.identity import APP_NAME, ORGANIZATION

if TYPE_CHECKING:
    from app.ai.creative_workflow_service import CreativeWorkflowService
    from app.channels.channel_service import ChannelService
    from app.core.storage import Storage
    from app.diagnostics.startup_profiler import StartupProfile
    from app.pipelines.engine import ProductionEngine
    from app.projects.project_service import ProjectService
    from app.providers.forge_status import ForgeStatusService
    from app.tasks.generation_queue import GenerationQueue
    from app.tasks.task_manager import TaskManager


class AtlasApplication(QApplication):
    """Owns application lifecycle, theme, storage, channels, projects, and production."""

    storage: Storage
    channels: ChannelService
    projects: ProjectService
    production: ProductionEngine
    tasks: TaskManager
    generation: GenerationQueue
    forge_status: ForgeStatusService

    def __init__(self, argv: list[str], *, auto_bootstrap: bool = True) -> None:
        profiler = StartupProfiler.instance()
        profiler.begin("qapplication_construct")
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.setOrganizationName(ORGANIZATION)

        profiler.begin("app_icon")
        from app.ui.branding.icons import app_icon

        self.setWindowIcon(app_icon())
        profiler.end("app_icon")

        self.setStyle("Fusion")

        profiler.begin("theme_loading")
        from app.ui.theme.atlas_theme import apply_theme

        apply_theme(self)
        profiler.end("theme_loading")

        self._notification_host = None
        self._creative_workflow: CreativeWorkflowService | None = None
        self.startup_profile: StartupProfile | None = None
        self._production: ProductionEngine | None = None

        profiler.begin("core_qt_services")
        from app.providers.forge_status import ForgeStatusService
        from app.tasks.generation_queue import GenerationQueue
        from app.tasks.task_manager import TaskManager

        self.tasks = TaskManager(self)
        self.generation = GenerationQueue(self.tasks, parent=self)
        self.forge_status = ForgeStatusService(parent=self)
        profiler.end("core_qt_services")

        self._bootstrapped = False
        self.aboutToQuit.connect(self._on_about_to_quit)
        profiler.end("qapplication_construct")
        if auto_bootstrap:
            self.bootstrap()

    @property
    def production(self) -> ProductionEngine:  # type: ignore[override]
        if self._production is None:
            self.rebuild_production_engine()
        assert self._production is not None
        return self._production

    @production.setter
    def production(self, value: ProductionEngine) -> None:
        self._production = value

    def bootstrap(self, on_step: Callable[[str], None] | None = None) -> None:
        """Initialize core services. Safe to call once."""
        if self._bootstrapped:
            return

        profiler = StartupProfiler.instance()

        def step(label: str) -> None:
            if on_step is not None:
                on_step(label)

        profiler.begin("bootstrap_total")

        step("Storage")
        with profiler.stage("configuration_loading"):
            from app.core.ai_storage import apply_ai_storage_environment
            from app.core.storage import build_storage

            self.storage = build_storage()
            self.config = self.storage.config
            apply_ai_storage_environment(self.config.ai_models_root)

        # Atlas AI / plugin / runtime stacks are intentionally not started here.
        profiler.skip(
            "service_registry",
            "Not constructed at startup; created lazily with Creative Workflow / AI.",
        )
        profiler.skip(
            "runtime_registry",
            "Not constructed at startup; RuntimeManager loads on first AI analyze.",
        )
        profiler.skip(
            "plugin_discovery",
            "PluginManager not run at startup; Ollama plugin loads on first AI analyze.",
        )
        profiler.skip(
            "plugin_initialization",
            "Deferred until CreativeWorkflowService.ensure_ready().",
        )
        profiler.skip(
            "runtime_detection",
            "Ollama/Forge/FFmpeg runtime probes deferred (Forge poll starts async only).",
        )

        step("Channels")
        with profiler.stage("channel_service_init"):
            from app.channels.channel_service import ChannelService

            self.channels = ChannelService(self.storage, self.config)

        profiler.skip(
            "channel_loading",
            "Channel filesystem scan deferred until Channels / AI Workflow / Reviews open.",
        )

        step("Projects")
        with profiler.stage("project_service_init"):
            from app.projects.project_service import ProjectService

            self.projects = ProjectService(self.config)

        profiler.skip(
            "project_loading",
            "Project filesystem scan deferred until Projects / workspace / Reviews open.",
        )

        step("Project Intelligence")
        with profiler.stage("project_intelligence_import"):
            from app.projects import project_intelligence as _project_intelligence  # noqa: F401

        # Production engine + provider registries stay deferred until first use.
        step("Production Engine")
        profiler.skip(
            "production_engine",
            "ProductionEngine / pipelines / Forge / FFmpeg deferred until first production job.",
        )

        step("Forge Status")
        with profiler.stage("forge_status_start"):
            self.forge_status.update_settings(self.config.forge)
            self.forge_status.start()
            QTimer.singleShot(0, self.forge_status.ensure_running_if_configured)

        step("Ready")
        profiler.end("bootstrap_total")
        self._bootstrapped = True

    @property
    def creative_workflow(self) -> CreativeWorkflowService:
        """Lazy Creative Director bridge — constructed on first Analyze Script."""
        if self._creative_workflow is None:
            from app.ai.creative_workflow_service import CreativeWorkflowService

            install_root = Path(__file__).resolve().parents[1]
            self._creative_workflow = CreativeWorkflowService(install_root)
        return self._creative_workflow

    def rebuild_production_engine(self) -> None:
        """Recreate ProductionEngine after AI settings change."""
        from app.pipelines.engine import ProductionEngine
        from app.pipelines.registry import PipelineRegistry
        from app.providers.image_registry import ImageProviderRegistry
        from app.providers.registry import ProviderRegistry
        from app.providers.voice_registry import VoiceProviderRegistry

        registry = (
            self._production.registry
            if self._production is not None
            else PipelineRegistry()
        )
        self._production = ProductionEngine(
            self.projects,
            self.config,
            registry=registry,
            provider_registry=ProviderRegistry(self.config),
            image_provider_registry=ImageProviderRegistry(self.config),
            voice_provider_registry=VoiceProviderRegistry(self.config),
        )
        self.tasks.bind_engine(self._production)
        if getattr(self, "forge_status", None) is not None:
            self.forge_status.update_settings(self.config.forge)

    def set_notification_host(self, host: Any) -> None:
        self._notification_host = host

    def show_notification(self, title: str, message: str = "") -> None:
        host = self._notification_host
        if host is not None:
            host.show_toast(title, message)

    def _on_about_to_quit(self) -> None:
        """Stop polling; close Forge only when Atlas owns it and preference is set."""
        workflow = self._creative_workflow
        if workflow is not None:
            try:
                workflow.shutdown_runtimes()
            except Exception:  # noqa: BLE001
                pass

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
