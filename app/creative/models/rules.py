"""Creative rules — extensible identity constraints (not prompts)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.creative.models._util import from_dict, to_dict


@dataclass
class CreativeRule:
    """One enforceable creative constraint for a channel."""

    id: str
    title: str
    description: str = ""
    category: str = "general"  # brand|visual|thumbnail|movie|story|voice|music|general
    enabled: bool = True
    priority: int = 50
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CreativeRule:
        return from_dict(cls, data)


def default_rules() -> list[CreativeRule]:
    """Starter identity rules — channels may extend freely."""
    specs = (
        ("keep_channel_identity", "Always keep channel identity", "Every output must stay recognizable as this channel.", "brand", 100),
        ("use_channel_colors", "Use channel colors", "Prefer Brand Kit colors over random palettes.", "brand", 80),
        ("show_logo", "Show logo when useful", "Keep logo visible on thumbnails when space allows.", "brand", 75),
        ("no_cartoon", "No cartoon", "Never use cartoon or anime looks.", "visual", 100),
        ("cinematic_lighting", "Always cinematic", "Prefer cinematic lighting and depth.", "visual", 80),
        ("one_dominant_subject", "One main subject", "One clear hero subject per frame.", "visual", 90),
        ("dark_background", "Dark background bias", "Prefer darker, atmospheric backgrounds.", "visual", 60),
        ("warm_lighting", "Warm lighting bias", "Lean warm cinematic light unless story needs cold.", "visual", 55),
        ("thumb_max_four_words", "Maximum four words", "Thumbnail hooks stay short and readable.", "thumbnail", 90),
        ("thumb_high_contrast", "High contrast thumbnails", "Subjects and text must punch through.", "thumbnail", 80),
        ("story_curiosity_first", "Curiosity first", "Open with questions or impossible facts.", "story", 75),
        ("movie_slow_motion", "Controlled camera motion", "Keep motion elegant — rarely abrupt.", "movie", 70),
        ("voice_documentary", "Documentary narrator tone", "Calm authority over hype energy.", "voice", 70),
    )
    return [
        CreativeRule(
            id=rid,
            title=title,
            description=desc,
            category=cat,
            priority=priority,
        )
        for rid, title, desc, cat, priority in specs
    ]
