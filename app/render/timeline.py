"""Timeline models for the Render Service."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TimelineScene:
    """One visual beat on the main timeline."""

    index: int  # 1-based
    image_path: Path
    duration_sec: float
    motion: str
    transition: str = "fade"


@dataclass
class TimelineSegment:
    """Intro / Main / Outro — Intro and Outro reserved for future branding."""

    kind: str  # intro | main | outro
    scenes: list[TimelineScene] = field(default_factory=list)

    @property
    def duration_sec(self) -> float:
        return sum(max(0.0, scene.duration_sec) for scene in self.scenes)


@dataclass
class Timeline:
    """Full render plan. Music reserved; intro/outro segments may be empty."""

    segments: list[TimelineSegment]
    voice_path: Path | None = None
    music_path: Path | None = None  # reserved — not mixed in Sprint 8
    duration_source: str = "default_per_image"

    @property
    def main_scenes(self) -> list[TimelineScene]:
        for segment in self.segments:
            if segment.kind == "main":
                return list(segment.scenes)
        return []

    @property
    def total_duration_sec(self) -> float:
        return sum(segment.duration_sec for segment in self.segments)
