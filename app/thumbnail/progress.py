"""Progress payload for thumbnail jobs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThumbnailQueueProgress:
    message: str
    stage: str = ""
    elapsed_seconds: float = 0.0
