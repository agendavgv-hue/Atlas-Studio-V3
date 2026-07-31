"""Thumbnail settings — defaults for the Intelligent Thumbnail Engine."""

from __future__ import annotations

from dataclasses import dataclass

from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.quality.models import (
    DEFAULT_MAX_QUALITY_ATTEMPTS,
    DEFAULT_QUALITY_THRESHOLD,
)


@dataclass
class ThumbnailSettings:
    """Defaults for the Thumbnail Pipeline."""

    mode: str = ThumbnailMode.INTELLIGENT.value
    width: int = 1280
    height: int = 720
    seed: int = -1
    steps: int = 0
    cfg_scale: float = 0.0
    sampler: str = ""
    model: str = ""
    loras: list[str] | None = None
    primary_variant: str = "A"
    quality_threshold: int = DEFAULT_QUALITY_THRESHOLD
    max_quality_attempts: int = DEFAULT_MAX_QUALITY_ATTEMPTS

    def resolved_loras(self) -> list[str]:
        return [str(item).strip() for item in (self.loras or []) if str(item).strip()]
