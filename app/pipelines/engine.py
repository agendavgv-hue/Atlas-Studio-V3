"""ProductionEngine — heart of Atlas Studio production execution.

Coordinates pipelines today. Designed to later own Job Queue, notifications,
logging, retries, and provider execution without changing pipeline contracts.
"""

from __future__ import annotations

from pathlib import Path

from app.core.project_root import require_project_root
from app.pipelines.base import Pipeline
from app.pipelines.context import ChannelDefaults, PipelineContext
from app.pipelines.registry import PipelineRegistry
from app.pipelines.results import PipelineOutcome, PipelineResult
from app.pipelines.states import PipelineState
from app.projects.models import Project
from app.projects.project_paths import ProjectPaths
from app.projects.project_service import ProjectService
from app.projects.project_status import ProjectProgress


class ProductionEngine:
    """Execute pipelines against a project with shared lifecycle handling."""

    def __init__(
        self,
        project_service: ProjectService,
        registry: PipelineRegistry | None = None,
    ) -> None:
        self._projects = project_service
        self.registry = registry or PipelineRegistry()
        self._last_progress: ProjectProgress | None = None

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

    def execute(self, pipeline: Pipeline, context: PipelineContext) -> PipelineResult:
        """Validate, run, refresh intelligence on success, return structured result."""
        pipeline._cancel_requested = False
        pipeline._set_state(PipelineState.READY)
        pipeline._set_progress(0.0, "")
        pipeline._set_result(None)

        errors = pipeline.validate(context)
        if errors:
            result = PipelineResult.failed("Validation failed", errors=errors)
            pipeline._set_state(PipelineState.FAILED)
            pipeline._set_result(result)
            return result

        if pipeline.is_cancel_requested():
            result = PipelineResult.cancelled()
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

    def execute_registered(
        self,
        pipeline_id: str,
        context: PipelineContext,
    ) -> PipelineResult:
        """Create a pipeline from the registry and execute it (Job Queue ready)."""
        pipeline = self.registry.create(pipeline_id)
        return self.execute(pipeline, context)

    def _refresh_intelligence(self, context: PipelineContext) -> None:
        self._last_progress = self._projects.get_progress(
            context.channel_name,
            context.project_name,
        )
