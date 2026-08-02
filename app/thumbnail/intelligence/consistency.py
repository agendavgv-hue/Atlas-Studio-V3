"""Thumbnail consistency scoring — Critic-ready report shape."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.thumbnail.intelligence.context import ThumbnailIntelligenceContext


@dataclass
class ThumbnailConsistencyScore:
    brand: float = 100.0
    style: float = 100.0
    layout: float = 100.0
    identity: float = 100.0
    overall: float = 100.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_critic_dimensions(self) -> dict[str, float]:
        return {
            "brand": self.brand,
            "style": self.style,
            "composition": self.layout,
            "identity": self.identity,
            "overall": self.overall,
        }


def score_thumbnail_consistency(
    intelligence: ThumbnailIntelligenceContext,
    *,
    prompt: str = "",
    hook: str = "",
) -> ThumbnailConsistencyScore:
    """Heuristic consistency vs Director / Brand / DNA (no generation)."""
    blob = f"{prompt} {hook}".casefold()
    brand = 100.0
    style = 100.0
    layout = 100.0
    identity = 100.0
    notes: list[str] = []

    if intelligence.brand and intelligence.brand.primary_color:
        token = intelligence.brand.primary_color.casefold().lstrip("#")
        if token and token not in blob and intelligence.brand.primary_color.casefold() not in blob:
            brand -= 8
            notes.append("primary brand color weak in prompt")

    if intelligence.dna is not None:
        if intelligence.dna.layout.title_position and intelligence.dna.layout.title_position not in blob:
            layout -= 6
        if intelligence.dna.style.lighting and intelligence.dna.style.lighting.split("_")[0] not in blob:
            style -= 5
        identity -= 0  # DNA present boosts identity baseline

    if intelligence.director is not None:
        for rule in intelligence.director.enabled_rules():
            if rule.id == "no_cartoon" and any(t in blob for t in ("cartoon", "anime")):
                style -= 25
                notes.append("violates No Cartoon rule")
            if rule.id == "thumb_max_four_words" or "four words" in rule.title.casefold():
                words = [w for w in hook.split() if w.strip()]
                if words and len(words) > intelligence.studio.max_words:
                    layout -= 15
                    notes.append("hook exceeds max words")

    strength = intelligence.studio.style_strength / 100.0
    # Higher style strength → slightly stricter style expectation
    if strength > 0.7 and "cinematic" not in blob and intelligence.studio.thumbnail_style == "cinematic":
        style -= 4

    overall = round((brand + style + layout + identity) / 4.0, 2)
    return ThumbnailConsistencyScore(
        brand=max(0.0, brand),
        style=max(0.0, style),
        layout=max(0.0, layout),
        identity=max(0.0, identity),
        overall=overall,
        notes=notes,
    )
