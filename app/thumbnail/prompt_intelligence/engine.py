"""Prompt Intelligence Engine — craft model-aware block prompts (no new AI steps)."""

from __future__ import annotations

from dataclasses import dataclass

from app.thumbnail.anti_ai import AntiAiRules
from app.thumbnail.composition import CompositionPlan, BACKGROUND_SHARE, HERO_SHARE, NEGATIVE_SPACE_SHARE
from app.thumbnail.dna_loader import ChannelDNA
from app.thumbnail.prompt_intelligence.assembler import assemble_prompt
from app.thumbnail.prompt_intelligence.blocks import PromptBlocks
from app.thumbnail.prompt_intelligence.model_profiles import (
    ModelProfileLoader,
    ModelPromptProfile,
)
from app.thumbnail.prompt_intelligence.scorer import PromptQualityScore, score_prompt
from app.thumbnail.style_loader import ChannelThumbnailStyle
from app.thumbnail.thumbnail_director import ThumbnailStrategy


@dataclass(frozen=True)
class BuiltPrompt:
    """Result of Prompt Intelligence assembly for one variant."""

    prompt: str
    negative_prompt: str
    blocks: PromptBlocks
    profile: ModelPromptProfile
    quality: PromptQualityScore
    semantic_fixes: tuple[str, ...] = ()


class PromptIntelligenceEngine:
    """Turn creative decisions into professional, model-specific prompts."""

    def __init__(self, profile_loader: ModelProfileLoader | None = None) -> None:
        self._profiles = profile_loader or ModelProfileLoader()

    def build(
        self,
        *,
        strategy: ThumbnailStrategy,
        hero_subject: str,
        composition: CompositionPlan,
        style: ChannelThumbnailStyle,
        dna: ChannelDNA,
        anti_ai: AntiAiRules,
        variant_mood: str = "",
        model_name: str = "",
    ) -> BuiltPrompt:
        profile = self._profiles.get_profile(model_name)
        blocks = self._build_blocks(
            strategy=strategy,
            hero=hero_subject,
            composition=composition,
            style=style,
            dna=dna,
            anti_ai=anti_ai,
            variant_mood=variant_mood,
            profile=profile,
        )
        prompt, negative, cleaned, fixes = assemble_prompt(blocks, profile)
        quality = score_prompt(
            prompt=prompt,
            blocks=cleaned,
            profile=profile,
            dna_signature=dna.signature or dna.display_name,
            semantic_fixes=fixes,
        )
        return BuiltPrompt(
            prompt=prompt,
            negative_prompt=negative,
            blocks=cleaned,
            profile=profile,
            quality=quality,
            semantic_fixes=tuple(fixes),
        )

    def _build_blocks(
        self,
        *,
        strategy: ThumbnailStrategy,
        hero: str,
        composition: CompositionPlan,
        style: ChannelThumbnailStyle,
        dna: ChannelDNA,
        anti_ai: AntiAiRules,
        variant_mood: str,
        profile: ModelPromptProfile,
    ) -> PromptBlocks:
        hero = (hero or strategy.hero_subject or "").strip()
        emotion = (strategy.emotion or "").strip()
        feeling = (strategy.dominant_feeling or emotion).strip()
        click = (strategy.click_reason or "").strip()

        subject = (
            f"single hero subject: {hero}, filling about {int(HERO_SHARE * 100)}% of the frame, "
            "one subject only, no secondary heroes"
        )
        environment = (
            f"{composition.background or style.background_style}, "
            f"supporting background only (~{int(BACKGROUND_SHARE * 100)}%), never competing with the hero"
        )
        lighting = composition.light_source or style.lighting
        composition_text = (
            f"{composition.hero_position or style.composition}, "
            f"{composition.negative_space}, "
            f"hero ~{int(HERO_SHARE * 100)}% / negative space ~{int(NEGATIVE_SPACE_SHARE * 100)}% / "
            f"background ~{int(BACKGROUND_SHARE * 100)}%, "
            f"clean simple composition, never busy, "
            f"{composition.focus}, {composition.depth}, {composition.contrast}"
        )
        camera = composition.camera_angle or style.camera
        mood_parts = [
            emotion and f"{emotion} mood",
            feeling and f"viewer feeling: {feeling}",
            click and f"click motive: {click}",
            composition.emotion_accent,
            variant_mood,
        ]
        mood = ", ".join(part for part in mood_parts if part)
        style_text = ", ".join(
            part
            for part in (
                style.style,
                dna.signature,
                " ".join(dna.identity_rules[:2]) if dna.identity_rules else "",
            )
            if part
        )
        materials = composition.texture or style.texture
        colors = ", ".join(
            part
            for part in (
                dna.color_language.primary and f"primary {dna.color_language.primary}",
                dna.color_language.secondary and f"secondary {dna.color_language.secondary}",
                dna.color_language.accent and f"accent {dna.color_language.accent}",
                style.colors,
            )
            if part
        )
        quality_parts = list(profile.quality_tags)
        quality_parts.extend(
            [
                "YouTube thumbnail clarity",
                "instant readability at small size",
                style.thumbnail_rules,
            ]
        )
        if profile.cinematography_bias:
            quality_parts.insert(0, "cinematic still frame")
        quality = ", ".join(part for part in quality_parts if part)
        negative = anti_ai.merge_negative(style.negative_prompt)

        return PromptBlocks(
            subject=subject,
            environment=environment,
            lighting=lighting,
            composition=composition_text,
            camera=camera,
            mood=mood,
            style=style_text,
            materials=materials,
            color_palette=colors,
            quality=quality,
            negative_prompt=negative,
            extras={
                "channel": dna.display_name,
                "variant_mood": variant_mood,
                "model_profile": profile.key,
            },
        )
