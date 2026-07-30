"""Thumbnail settings — defaults for selection and generation snapshots.

Settings UI wiring is deferred; these defaults keep the selector independent.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.thumbnail.modes import ThumbnailMode


@dataclass
class ThumbnailSettings:
    """Persisted-style defaults for the Thumbnail Pipeline."""

    mode: str = ThumbnailMode.SELECT.value
    width: int = 1280
    height: int = 720
    seed: int = -1
    # Reserved for when Service builds ImageGenerationRequest.
    steps: int = 0
    cfg_scale: float = 0.0
    sampler: str = ""
    model: str = ""
