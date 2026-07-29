"""Abstract pipeline interface — every production step implements this."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.pipelines.states import PipelineState


class Pipeline(ABC):
    """Common lifecycle for Script, Images, Voice, Movie, and all future steps.

    Future providers (Forge, Gemini, Ollama, LM Studio) are called from
    concrete ``run`` implementations — not from this base class.
    """

    def __init__(self) -> None:
        self._state = PipelineState.READY
        self._progress = 0.0
        self._progress_message = ""
        self._cancel_requested = False
        self._result: PipelineResult | None = None

    @property
    @abstractmethod
    def pipeline_id(self) -> str:
        """Stable id used by registry / future Job Queue (e.g. ``script``)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable pipeline name."""

    def validate(self, context: PipelineContext) -> list[str]:
        """Return validation error messages; empty means OK."""
        errors: list[str] = []
        if not context.project_dir.is_dir():
            errors.append(f"Project folder not found: {context.project_dir}")
        return errors

    @abstractmethod
    def run(self, context: PipelineContext) -> PipelineResult:
        """Execute the pipeline. Subclasses perform real work in later sprints."""

    def cancel(self) -> None:
        """Request cooperative cancellation; checked by long-running pipelines."""
        self._cancel_requested = True

    def status(self) -> PipelineState:
        return self._state

    def progress(self) -> tuple[float, str]:
        return self._progress, self._progress_message

    def result(self) -> PipelineResult | None:
        return self._result

    def is_cancel_requested(self) -> bool:
        return self._cancel_requested

    def _set_state(self, state: PipelineState) -> None:
        self._state = state

    def _set_progress(self, value: float, message: str = "") -> None:
        self._progress = max(0.0, min(1.0, value))
        self._progress_message = message

    def _set_result(self, result: PipelineResult) -> None:
        self._result = result
