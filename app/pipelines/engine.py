"""ProductionEngine — heart of Atlas Studio production execution.

Coordinates pipelines, chaining, providers, intelligence refresh, and
structured results. Designed for future Job Queue, retries, and logging.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from app.core.app_config import AppConfig
from app.core.project_root import require_project_root
from app.pipelines.base import Pipeline
from app.pipelines.context import ChannelDefaults, PipelineContext
from app.pipelines.production_sheet_pipeline import ProductionSheetPipeline
from app.pipelines.registry import PipelineRegistry
from app.pipelines.results import PipelineOutcome, PipelineResult
from app.pipelines.script_pipeline import ScriptPipeline
from app.pipelines.states import PipelineState
from app.projects.models import Project
from app.projects.project_paths import ProjectPaths
from app.projects.project_service import ProjectService
from app.projects.project_status import ProjectProgress
from app.prompts.assembler import PromptAssembler
from app.providers.base import TextProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.registry import ProviderRegistry


class ProductionEngine:
    """Execute pipelines against a project with shared lifecycle handling."""

    def __init__(
        self,
        project_service: ProjectService,
        config: AppConfig,
        registry: PipelineRegistry | None = None,
        provider_registry: ProviderRegistry | None = None,
        *,
        text_provider: TextProvider | None = None,
        prompts: PromptAssembler | None = None,
    ) -> None:
        self._projects = project_service
        self._config = config
        self.registry = registry or PipelineRegistry()
        self._providers = provider_registry or ProviderRegistry(config)
        self._text_provider_override = text_provider  # tests only
        self._prompts = prompts or PromptAssembler()
        self._last_progress: ProjectProgress | None = None
        self._register_defaults()

    @property
    def last_progress(self) -> ProjectProgress | None:
        return self._last_progress

    def build_context(
        self,
        project: Project,
        channel_defaults: ChannelDefaults | None = None,
    ) -> PipelineContext:
        root = require_project_root(self._projects.project_root)
        paths = ProjectPaths(root, project.channel_name)
        project_dir = paths.project_dir(project.folder_name)
        return PipelineContext(
            project=project,
            project_dir=project_dir,
            channel_defaults=channel_defaults or ChannelDefaults(name=project.channel_name),
        )

    def resolve_text_provider(self) -> TextProvider:
        if self._text_provider_override is not None:
            return self._text_provider_override
        return self._providers.require_text_provider()

    def execute(self, pipeline: Pipeline, context: PipelineContext) -> PipelineResult:
        """Validate, run, refresh intelligence on success, return structured result."""
        started = time.perf_counter()
        pipeline._cancel_requested = False
        pipeline._set_state(PipelineState.READY)
        pipeline._set_progress(0.0, "")
        pipeline._set_result(None)

        errors = pipeline.validate(context)
        if errors:
            result = PipelineResult.failed(
                "Validation failed",
                errors=errors,
                execution_time_ms=self._elapsed_ms(started),
            )
            pipeline._set_state(PipelineState.FAILED)
            pipeline._set_result(result)
            return result

        if pipeline.is_cancel_requested():
            result = PipelineResult.cancelled(execution_time_ms=self._elapsed_ms(started))
            pipeline._set_state(PipelineState.CANCELLED)
            pipeline._set_result(result)
            return result

        pipeline._set_state(PipelineState.RUNNING)
        pipeline._set_progress(0.0, "Running")

        try:
            result = pipeline.run(context)
        except Exception as exc:  # noqa: BLE001 — boundary for all pipelines
            result = PipelineResult.failed(str(exc), errors=[str(exc)])

        if pipeline.is_cancel_requested() and result.outcome != PipelineOutcome.CANCELLED:
            result = PipelineResult.cancelled(result.message or "Cancelled")

        result.execution_time_ms = self._elapsed_ms(started)

        if result.outcome == PipelineOutcome.CANCELLED:
            pipeline._set_state(PipelineState.CANCELLED)
        elif result.outcome == PipelineOutcome.FAILED:
            pipeline._set_state(PipelineState.FAILED)
        else:
            pipeline._set_state(PipelineState.COMPLETED)

        pipeline._set_progress(result.progress, result.message)
        pipeline._set_result(result)

        if result.ok:
            self._refresh_intelligence(context)

        return result

    def execute_chain(
        self,
        pipelines: Sequence[Pipeline],
        context: PipelineContext,
    ) -> PipelineResult:
        """Run pipelines sequentially; stop on first non-ok result."""
        started = time.perf_counter()
        artifacts: list[str] = []
        last = PipelineResult.failed("No pipelines provided")

        for pipeline in pipelines:
            last = self.execute(pipeline, context)
            artifacts.extend(last.artifacts)
            if not last.ok:
                last.artifacts = list(dict.fromkeys(artifacts))
                last.execution_time_ms = self._elapsed_ms(started)
                return last

        return PipelineResult.success(
            "Production chain completed",
            artifacts=list(dict.fromkeys(artifacts)),
            execution_time_ms=self._elapsed_ms(started),
        )

    def generate_production(
        self,
        context: PipelineContext,
        *,
        topic: str | None = None,
    ) -> PipelineResult:
        """Primary user workflow: Script → Production Sheet."""
        try:
            provider = self.resolve_text_provider()
        except ProviderConfigurationError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])

        topic_value = (topic or context.project.idea or context.project.name).strip()
        script = ScriptPipeline(provider, self._prompts, topic=topic_value)
        sheet = ProductionSheetPipeline(provider, self._prompts)
        return self.execute_chain([script, sheet], context)

    def regenerate_script(
        self,
        context: PipelineContext,
        *,
        topic: str | None = None,
    ) -> PipelineResult:
        try:
            provider = self.resolve_text_provider()
        except ProviderConfigurationError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])
        topic_value = (topic or context.project.idea or context.project.name).strip()
        return self.execute(
            ScriptPipeline(provider, self._prompts, topic=topic_value),
            context,
        )

    def regenerate_production_sheet(self, context: PipelineContext) -> PipelineResult:
        try:
            provider = self.resolve_text_provider()
        except ProviderConfigurationError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])

        from app.pipelines.artifacts import SCRIPT_FILENAME, SCRIPT_FOLDER

        script_path = context.folder(SCRIPT_FOLDER) / SCRIPT_FILENAME
        if not script_path.is_file():
            # Auto-generate script first, then sheet.
            return self.generate_production(context)

        return self.execute(ProductionSheetPipeline(provider, self._prompts), context)

    def execute_registered(
        self,
        pipeline_id: str,
        context: PipelineContext,
    ) -> PipelineResult:
        pipeline = self.registry.create(pipeline_id)
        return self.execute(pipeline, context)

    def _register_defaults(self) -> None:
        # Factories require a provider at create-time — register lazy wrappers later
        # via execute_registered when Job Queue lands. Milestone 1 uses generate_*.
        return

    def _refresh_intelligence(self, context: PipelineContext) -> None:
        self._last_progress = self._projects.get_progress(
            context.channel_name,
            context.project_name,
        )

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)
