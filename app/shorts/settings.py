"""Shorts settings — defaults for planning and generation snapshots."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShortsSettings:
    """Persisted-style defaults for the Shorts Pipeline."""

    # Sprint 10 default: one short; API still returns list[ShortsDefinition].
    max_shorts: int = 1
    default_duration_sec: float = 3.0
    max_duration_sec: float = 60.0
    motion: str = "none"
    framing: str = "center_crop"
    transition: str = "cut"
    use_voice_when_available: bool = True
    width: int = 1080
    height: int = 1920
    fps: int = 30
    profile: str = "shorts"
    codec: str = "libx264"
    preset: str = "medium"
    crf: int = 23
