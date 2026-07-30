"""Scene duration resolution — Production Sheet first, then voice/default fallbacks.

Production Sheet duration parsing is owned by ``app.pipelines.sheet_prompts``.
This module only orchestrates duration strategy for the Movie/Render path.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.pipelines.sheet_prompts import extract_sheet_durations

__all__ = [
    "extract_sheet_durations",
    "natural_image_sort_key",
    "resolve_scene_durations",
]


def resolve_scene_durations(
    *,
    image_count: int,
    sheet_text: str | None,
    voice_duration_sec: float | None,
    default_duration_sec: float,
) -> tuple[list[float], str]:
    """Return (durations, source_id). Never hardcodes a single strategy.

    Preference order:
    1. Production Sheet per-scene durations (shared sheet parser)
    2. Equal split of voice narration length
    3. Configurable default duration per image
    """
    if image_count < 1:
        return [], "empty"

    if sheet_text:
        sheet = extract_sheet_durations(sheet_text, image_count)
        if sheet is not None:
            return sheet, "production_sheet"

    if voice_duration_sec is not None and voice_duration_sec > 0:
        each = max(0.5, float(voice_duration_sec) / image_count)
        return [each] * image_count, "voice_equal_split"

    each = max(0.5, float(default_duration_sec))
    return [each] * image_count, "default_per_image"


def natural_image_sort_key(path: Path) -> tuple:
    """Sort image_01 before image_10."""
    parts = re.split(r"(\d+)", path.name.casefold())
    key: list = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part)
    return tuple(key)
