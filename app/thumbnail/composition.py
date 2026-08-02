"""Composition Planner — frame geometry for CTR-focused thumbnails.

Layout ratios are fixed marketing rules; visual language comes from
``channel_style.json`` (never hardcoded per channel in code).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.models.thumbnail_dna import ThumbnailDNA
from app.thumbnail.style_loader import ChannelThumbnailStyle
from app.thumbnail.thumbnail_director import ThumbnailStrategy

# Marketing composition ratios (not channel-specific art direction).
HERO_SHARE = 0.40
NEGATIVE_SPACE_SHARE = 0.35
BACKGROUND_SHARE = 0.25


@dataclass(frozen=True)
class CompositionPlan:
    """Automatic frame plan for one thumbnail generation."""

    hero_position: str
    light_source: str
    camera_angle: str
    background: str
    negative_space: str
    focus: str
    hero_scale: str
    depth: str
    contrast: str
    texture: str
    headline_position: str
    emotion_accent: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def prompt_block(self) -> str:
        parts = [
            f"composition: hero ~{int(HERO_SHARE * 100)}%, "
            f"negative space ~{int(NEGATIVE_SPACE_SHARE * 100)}%, "
            f"background ~{int(BACKGROUND_SHARE * 100)}%",
            f"hero position: {self.hero_position}",
            f"hero scale: {self.hero_scale}",
            f"light source: {self.light_source}",
            f"camera: {self.camera_angle}",
            f"background: {self.background}",
            f"negative space: {self.negative_space}",
            f"focus: {self.focus}",
            f"depth: {self.depth}",
            f"contrast: {self.contrast}",
            f"texture: {self.texture}",
            f"headline area: {self.headline_position}",
        ]
        if self.emotion_accent:
            parts.append(f"emotional accent: {self.emotion_accent}")
        return "; ".join(part for part in parts if part.split(": ", 1)[-1].strip())


class CompositionPlanner:
    """Build a clean CTR composition from channel style + strategy emotion."""

    def plan(
        self,
        *,
        strategy: ThumbnailStrategy,
        style: ChannelThumbnailStyle,
        thumbnail_dna: ThumbnailDNA | None = None,
    ) -> CompositionPlan:
        emotion = (strategy.emotion or "").strip()
        title_side = (style.headline_position or "left").strip() or "left"
        hero_pos = style.composition or (
            "hero on the right third, facing into open left space"
        )
        light = style.lighting
        contrast = style.contrast
        hero_scale = style.hero_scale or (
            f"hero fills about {int(HERO_SHARE * 100)}% of the frame"
        )
        focus = "single sharp hero subject, everything else simpler and darker"

        if thumbnail_dna is not None:
            title_side = thumbnail_dna.layout.title_position or title_side
            subject = thumbnail_dna.layout.subject_position or "right"
            hero_pos = (
                f"hero subject on the {subject}, open {title_side} for headline"
            )
            light = thumbnail_dna.style.lighting or light
            contrast = thumbnail_dna.style.contrast or contrast
            scale = thumbnail_dna.composition.subject_scale or "large"
            hero_scale = f"hero subject scale {scale} (~{int(HERO_SHARE * 100)}% of frame)"
            focus = (
                f"{thumbnail_dna.composition.focus or 'hero'} focus, "
                f"gaze {thumbnail_dna.composition.gaze_direction or 'into_frame'}"
            )
            neg_side = thumbnail_dna.layout.negative_space or title_side
        else:
            neg_side = title_side

        return CompositionPlan(
            hero_position=hero_pos,
            light_source=light,
            camera_angle=style.camera,
            background=style.background_style,
            negative_space=(
                f"clean {int(NEGATIVE_SPACE_SHARE * 100)}% negative space on the "
                f"{neg_side} for the headline; never busy"
            ),
            focus=focus,
            hero_scale=hero_scale,
            depth=style.depth,
            contrast=contrast,
            texture=style.texture,
            headline_position=title_side,
            emotion_accent=_emotion_accent(
                emotion or (thumbnail_dna.style.emotion if thumbnail_dna else "")
            ),
        )


def _emotion_accent(emotion: str) -> str:
    """Generic CTR accents keyed by emotion name — not channel-specific."""
    mapping = {
        "Mystery": "shadows, unanswered visual question, half-revealed detail",
        "Shock": "sudden reveal energy, stark highlight on the impossible detail",
        "Fear": "ominous edge light, tense empty space",
        "Discovery": "beam of revelation light hitting the hero",
        "Wonder": "scale contrast, luminous atmosphere",
        "Curiosity": "partially obscured hero, inviting gap on headline side",
        "Urgency": "diagonal tension, strong directional light",
        "Awe": "low angle monumentality, vast depth",
        "Suspense": "compressed depth, waiting-before-impact stillness",
    }
    return mapping.get(emotion, "strong emotional clarity, high readability")
