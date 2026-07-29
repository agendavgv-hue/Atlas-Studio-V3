"""Project progress status models (intelligence output)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressStep:
    key: str
    label: str
    complete: bool

    @property
    def display(self) -> str:
        mark = "✔" if self.complete else "✖"
        return f"{mark} {self.label}"


@dataclass(frozen=True)
class ProjectProgress:
    steps: tuple[ProgressStep, ...]

    def step(self, key: str) -> ProgressStep | None:
        for item in self.steps:
            if item.key == key:
                return item
        return None


# Ordered progress keys shown in workspace / future dashboard.
PROGRESS_STEP_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("script", "Script"),
    ("production_sheet", "Production Sheet"),
    ("images", "Images"),
    ("instagram", "Instagram"),
    ("movie", "Movie"),
    ("shorts", "Shorts"),
    ("thumbnail", "Thumbnail"),
    ("youtube_export", "YouTube Export"),
)
