"""Thumbnail Intelligence Prompt Builder — style from Director/DNA, never hardcoded."""

from __future__ import annotations

from dataclasses import dataclass

from app.thumbnail.intelligence.branding import ThumbnailBrandingService
from app.thumbnail.intelligence.context import ThumbnailIntelligenceContext
from app.thumbnail.intelligence.planner import ThumbnailPlan


@dataclass(frozen=True)
class BuiltThumbnailPrompt:
    prompt: str
    negative_prompt: str
    style_block: str
    brand_block: str


class ThumbnailIntelligencePromptBuilder:
    """Compose a professional thumbnail prompt AFTER planning/concept choice."""

    def __init__(self, branding: ThumbnailBrandingService | None = None) -> None:
        self._branding = branding or ThumbnailBrandingService()

    def build(
        self,
        *,
        plan: ThumbnailPlan,
        intelligence: ThumbnailIntelligenceContext,
        hero_subject: str = "",
        hook: str = "",
        extra_negative: str = "",
    ) -> BuiltThumbnailPrompt:
        studio = intelligence.studio
        strength = studio.style_strength / 100.0
        brand_block = self._branding.branding_prompt_block(
            intelligence.brand,
            settings=studio,
            placement=intelligence.logo_placement,
        )
        dna_block = intelligence.dna.prompt_block() if intelligence.dna else ""
        director_visual = ""
        if intelligence.director is not None:
            v = intelligence.director.visual
            t = intelligence.director.thumbnail
            director_visual = (
                f"director look: {v.realism}, cinematic {v.cinematic}, "
                f"lighting {v.lighting}, contrast {v.contrast}, depth {v.depth}, "
                f"palette {v.color_palette}; "
                f"layout {t.layout}, text {t.text_position}, "
                f"subject scale {t.subject_scale}, negative space {t.negative_space}, "
                f"max {studio.max_words} words, CTR {t.ctr_style}"
            )

        concept = plan.concept_plan.chosen
        hero = (hero_subject or plan.strategy.hero_subject or concept.idea or "").strip()
        emotion = plan.strategy.emotion
        click = plan.strategy.click_reason

        style_parts = [
            f"style strength {strength:.2f}",
            f"quality {studio.quality}",
            f"creativity {studio.creativity:g}/100",
            f"contrast {studio.contrast}",
            f"negative space {studio.negative_space}",
            dna_block,
            director_visual,
            brand_block,
        ]
        if intelligence.style is not None:
            style_parts.append(
                f"library thumb style {intelligence.style.thumbnail_style}; "
                f"mystery {intelligence.style.mystery:g}; darkness {intelligence.style.darkness:g}"
            )
        style_block = "; ".join(p for p in style_parts if p)

        prompt = (
            f"YouTube thumbnail still, single hero: {hero}. "
            f"Concept '{concept.title}': {concept.idea}. "
            f"Emotion {emotion}. Click reason: {click}. "
            f"Open {studio.negative_space} third for headline overlay "
            f"(max {studio.max_words} words — do NOT paint text). "
            f"{style_block}"
        )
        if hook:
            prompt += f" Headline intent (overlay later): {hook}."

        negative = (
            "text, letters, watermark, logo baked in, collage, split screen, "
            "cartoon, anime, low contrast, cluttered composition, multiple heroes, "
            "busy background"
        )
        if extra_negative:
            negative = f"{negative}, {extra_negative}"

        return BuiltThumbnailPrompt(
            prompt=" ".join(prompt.split()),
            negative_prompt=negative,
            style_block=style_block,
            brand_block=brand_block,
        )
