"""SceneSelection — ordered scenes chosen by ShortsSelector.

Planner turns this into ShortsDefinitions; Selector never splits or plans shorts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SelectedScene:
    """One selected scene candidate (not yet a ShortsDefinition)."""

    order: int  # 1-based position in the selection
    image_path: str
    sheet_index: int | None = None
    sheet_ref: str = ""
    duration_sec: float | None = None  # from production sheet when present
    label: str = ""


@dataclass(frozen=True)
class SceneSelection:
    """Immutable selector output — scenes only."""

    scenes: tuple[SelectedScene, ...]
    source: str  # production_sheet | images_fallback
    rationale: str = ""

    @property
    def count(self) -> int:
        return len(self.scenes)

    def image_paths(self) -> list[Path]:
        return [Path(scene.image_path) for scene in self.scenes]
