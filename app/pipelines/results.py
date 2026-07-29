"""Structured pipeline outcomes for UI and future Job Queue."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PipelineOutcome(str, Enum):
    SUCCESS = "Success"
    WARNING = "Warning"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass
class PipelineResult:
    outcome: PipelineOutcome
    message: str = ""
    errors: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    progress: float = 0.0
    execution_time_ms: float = 0.0
    # Image queue / Retry Failed support (optional for other pipelines).
    queue_current: int = 0
    queue_total: int = 0
    failed_indexes: list[int] = field(default_factory=list)
    succeeded_indexes: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.outcome in {PipelineOutcome.SUCCESS, PipelineOutcome.WARNING}

    @classmethod
    def success(
        cls,
        message: str = "",
        *,
        artifacts: list[str] | None = None,
        progress: float = 1.0,
        execution_time_ms: float = 0.0,
        queue_current: int = 0,
        queue_total: int = 0,
        failed_indexes: list[int] | None = None,
        succeeded_indexes: list[int] | None = None,
    ) -> PipelineResult:
        return cls(
            outcome=PipelineOutcome.SUCCESS,
            message=message,
            artifacts=list(artifacts or []),
            progress=progress,
            execution_time_ms=execution_time_ms,
            queue_current=queue_current,
            queue_total=queue_total,
            failed_indexes=list(failed_indexes or []),
            succeeded_indexes=list(succeeded_indexes or []),
        )

    @classmethod
    def warning(
        cls,
        message: str,
        *,
        errors: list[str] | None = None,
        artifacts: list[str] | None = None,
        progress: float = 1.0,
        execution_time_ms: float = 0.0,
        queue_current: int = 0,
        queue_total: int = 0,
        failed_indexes: list[int] | None = None,
        succeeded_indexes: list[int] | None = None,
    ) -> PipelineResult:
        return cls(
            outcome=PipelineOutcome.WARNING,
            message=message,
            errors=list(errors or []),
            artifacts=list(artifacts or []),
            progress=progress,
            execution_time_ms=execution_time_ms,
            queue_current=queue_current,
            queue_total=queue_total,
            failed_indexes=list(failed_indexes or []),
            succeeded_indexes=list(succeeded_indexes or []),
        )

    @classmethod
    def failed(
        cls,
        message: str,
        *,
        errors: list[str] | None = None,
        progress: float = 0.0,
        execution_time_ms: float = 0.0,
        queue_current: int = 0,
        queue_total: int = 0,
        failed_indexes: list[int] | None = None,
        succeeded_indexes: list[int] | None = None,
    ) -> PipelineResult:
        return cls(
            outcome=PipelineOutcome.FAILED,
            message=message,
            errors=list(errors or [message]),
            progress=progress,
            execution_time_ms=execution_time_ms,
            queue_current=queue_current,
            queue_total=queue_total,
            failed_indexes=list(failed_indexes or []),
            succeeded_indexes=list(succeeded_indexes or []),
        )

    @classmethod
    def cancelled(
        cls,
        message: str = "Cancelled",
        *,
        execution_time_ms: float = 0.0,
        queue_current: int = 0,
        queue_total: int = 0,
        failed_indexes: list[int] | None = None,
        succeeded_indexes: list[int] | None = None,
        artifacts: list[str] | None = None,
    ) -> PipelineResult:
        return cls(
            outcome=PipelineOutcome.CANCELLED,
            message=message,
            progress=0.0,
            execution_time_ms=execution_time_ms,
            artifacts=list(artifacts or []),
            queue_current=queue_current,
            queue_total=queue_total,
            failed_indexes=list(failed_indexes or []),
            succeeded_indexes=list(succeeded_indexes or []),
        )
