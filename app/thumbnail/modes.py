"""Thumbnail generation modes.

Selector chooses a mode; Generator and Exporter do not.
"""

from __future__ import annotations

from enum import Enum


class ThumbnailMode(str, Enum):
    """How the thumbnail source is decided."""

    GENERATE = "generate"  # Mode 1 — new image from a prepared provider request
    SELECT = "select"  # Mode 2 — use one existing project image
    CANDIDATES = "candidates"  # Mode 3 — choose among several options (no disk candidates folder)
    AI_SCORED = "ai_scored"  # Mode 4 — reserved; not implemented in Sprint 9
