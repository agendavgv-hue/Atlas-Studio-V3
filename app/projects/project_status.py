"""Project progress status models (intelligence output)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressStep:
    key: str
    label: str
    complete: bool
    running: bool = False  # Reserved for future Job Queue

    @property
    def state(self) -> str:
        if self.running:
            return "running"
        if self.complete:
            return "complete"
        return "missing"


@dataclass(frozen=True)
class ProjectProgress:
    steps: tuple[ProgressStep, ...]

    def step(self, key: str) -> ProgressStep | None:
        for item in self.steps:
            if item.key == key:
                return item
        return None


# Workspace order — production progress only.
PROGRESS_STEP_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("script", "Script"),
    ("production_sheet", "Production Sheet"),
    ("images", "Images"),
    ("voice", "Voice"),
    ("instagram", "Instagram"),
    ("shorts", "Shorts"),
    ("movie", "Movie"),
    ("thumbnail", "Thumbnail"),
    ("youtube_export", "YouTube Export"),
)
