"""Scene motion selection and FFmpeg video filter helpers."""

from __future__ import annotations

import random

from app.core.movie_settings import MOTION_STYLES

_CONCRETE = tuple(style for style in MOTION_STYLES if style != "random")


def resolve_motion(style: str, *, index: int, seed: int | None = None) -> str:
    """Resolve configured motion to a concrete per-scene style."""
    value = (style or "none").strip().casefold()
    if value == "random":
        rng = random.Random((seed or 0) ^ (index * 2654435761))
        return rng.choice(_CONCRETE)
    if value in _CONCRETE:
        return value
    return "none"


def scene_video_filter(
    *,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
    motion: str,
) -> str:
    """Build an FFmpeg ``-vf`` chain for one still image scene."""
    frames = max(1, int(round(duration_sec * fps)))
    w, h = int(width), int(height)
    base = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h}"
    )
    style = (motion or "none").casefold()
    if style == "zoom_in":
        # Gentle Ken Burns zoom toward center.
        return (
            f"{base},"
            f"zoompan=z='min(1.0+0.0012*on,1.25)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={w}x{h}:fps={fps}"
        )
    if style == "zoom_out":
        return (
            f"{base},"
            f"zoompan=z='if(eq(on,1),1.25,max(1.25-0.0012*on,1.0))':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={w}x{h}:fps={fps}"
        )
    if style == "pan_left":
        return (
            f"{base},"
            f"zoompan=z='1.12':"
            f"x='(iw-iw/zoom)*(1-on/{frames})':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={w}x{h}:fps={fps}"
        )
    if style == "pan_right":
        return (
            f"{base},"
            f"zoompan=z='1.12':"
            f"x='(iw-iw/zoom)*(on/{frames})':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={w}x{h}:fps={fps}"
        )
    # none — static framed still
    return f"{base},fps={fps}"
