"""Thumbnail generation modes.

Intelligent is the default professional YouTube designer path.
Select remains available as a legacy copy-from-images fallback.
"""

from __future__ import annotations

from enum import Enum


class ThumbnailMode(str, Enum):
    """How the thumbnail is produced."""

    INTELLIGENT = "intelligent"  # Script → hero → hook → channel style → 4 variants
    GENERATE = "generate"  # Alias treated as intelligent by the service
    SELECT = "select"  # Legacy — copy one existing project image
    CANDIDATES = "candidates"
    AI_SCORED = "ai_scored"
