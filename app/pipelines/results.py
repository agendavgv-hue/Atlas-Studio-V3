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
    ) -> PipelineResult:
        return cls(
            outcome=PipelineOutcome.SUCCESS,
            message=message,
            artifacts=list(artifacts or []),
            progress=progress,
        )

    @classmethod
    def warning(
        cls,
        message: str,
        *,
        errors: list[str] | None = None,
        artifacts: list[str] | None = None,
        progress: float = 1.0,
    ) -> PipelineResult:
        return cls(
            outcome=PipelineOutcome.WARNING,
            message=message,
            errors=list(errors or []),
            artifacts=list(artifacts or []),
            progress=progress,
        )

    @classmethod
    def failed(
        cls,
        message: str,
        *,
        errors: list[str] | None = None,
        progress: float = 0.0,
    ) -> PipelineResult:
        return cls(
            outcome=PipelineOutcome.FAILED,
            message=message,
            errors=list(errors or [message]),
            progress=progress,
        )

    @classmethod
    def cancelled(cls, message: str = "Cancelled") -> PipelineResult:
        return cls(outcome=PipelineOutcome.CANCELLED, message=message, progress=0.0)
