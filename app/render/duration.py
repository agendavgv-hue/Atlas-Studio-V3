"""Scene duration resolution — Production Sheet first, then voice/default fallbacks."""

from __future__ import annotations

import re
from pathlib import Path

# Duration lines under an image/scene block, e.g. "Duration: 4.5" / "Duration: 4s"
_DURATION_LINE = re.compile(
    r"(?im)^\s*duration\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*(s|sec|secs|seconds)?\s*$"
)
_IMAGE_HEADER = re.compile(r"(?im)^\s*(?:IMAGE|Scene)\s*0*([0-9]+)\b")


def extract_sheet_durations(sheet_text: str, image_count: int) -> list[float] | None:
    """Try to read per-image durations from a Production Sheet.

    Returns a list of length ``image_count`` when every scene has a duration,
    otherwise ``None`` so callers fall back to another strategy.
    """
    if image_count < 1 or not (sheet_text or "").strip():
        return None

    lines = sheet_text.splitlines()
    by_index: dict[int, float] = {}
    current: int | None = None
    for line in lines:
        header = _IMAGE_HEADER.match(line)
        if header:
            current = int(header.group(1))
            continue
        if current is None:
            continue
        match = _DURATION_LINE.match(line)
        if match:
            by_index[current] = max(0.5, float(match.group(1)))

    if len(by_index) < image_count:
        return None
    durations = [by_index.get(i) for i in range(1, image_count + 1)]
    if any(value is None for value in durations):
        return None
    return [float(value) for value in durations]  # type: ignore[arg-type]


def resolve_scene_durations(
    *,
    image_count: int,
    sheet_text: str | None,
    voice_duration_sec: float | None,
    default_duration_sec: float,
) -> tuple[list[float], str]:
    """Return (durations, source_id). Never hardcodes a single strategy.

    Preference order:
    1. Production Sheet per-scene durations
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
