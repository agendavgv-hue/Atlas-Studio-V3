"""Progress payload for movie / render jobs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MovieQueueProgress:
    current: int
    total: int
    message: str
    stage: str = "scene"
    scene_label: str = ""
    elapsed_seconds: float = 0.0
    eta_seconds: float | None = None

    @property
    def short_label(self) -> str:
        text = (self.scene_label or "").strip()
        if len(text) <= 80:
            return text
        return text[:77] + "…"
