"""Project progress status models (intelligence output)."""

from __future__ import annotations

from dataclasses import dataclass

from app.projects.production_stages import VISIBLE_STAGES


@dataclass(frozen=True)
class ProgressStep:
    key: str
    label: str
    complete: bool
    running: bool = False
    failed: bool = False
    detail: str = ""

    @property
    def state(self) -> str:
        if self.running:
            return "running"
        if self.failed and not self.complete:
            return "failed"
        if self.complete:
            return "complete"
        return "not_started"


@dataclass(frozen=True)
class ProjectProgress:
    steps: tuple[ProgressStep, ...]

    def step(self, key: str) -> ProgressStep | None:
        for item in self.steps:
            if item.key == key:
                return item
        return None

    @property
    def percent_complete(self) -> int:
        if not self.steps:
            return 0
        done = sum(1 for s in self.steps if s.complete)
        return int(round(100.0 * done / len(self.steps)))


# Keep in sync with VISIBLE_STAGES (production hub order).
PROGRESS_STEP_DEFINITIONS: tuple[tuple[str, str], ...] = tuple(
    (s.key, s.label) for s in VISIBLE_STAGES
)
