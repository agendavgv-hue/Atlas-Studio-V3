"""Build provider-ready thumbnail prompts via Prompt Intelligence Engine.

No new AI steps — only structured blocks, model profiles, optimization,
semantic contradiction fixes, and prompt quality scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.thumbnail.anti_ai import AntiAiRules
from app.thumbnail.composition import CompositionPlan
from app.thumbnail.dna_loader import ChannelDNA
from app.thumbnail.prompt_intelligence import (
    BuiltPrompt,
    ModelProfileLoader,
    PromptIntelligenceEngine,
    PromptQualityScore,
)
from app.thumbnail.style_loader import ChannelThumbnailStyle
from app.thumbnail.thumbnail_director import ThumbnailStrategy

THUMBNAIL_VARIANTS: tuple[tuple[str, str, str], ...] = (
    ("A", "mystery", "unanswered visual question, restrained mystery"),
    ("B", "epic", "monumental scale, controlled awe"),
    ("C", "documentary", "grounded authenticity, museum stillness"),
    ("D", "dramatic", "high-stakes tension, sharp contrast"),
)


@dataclass(frozen=True)
class ThumbnailPromptPlan:
    """One variant ready for ImageProvider.generate_image."""

    variant_id: str
    variant_key: str
    variant_label: str
    prompt: str
    negative_prompt: str
    blocks: dict | None = None
    prompt_quality: dict | None = None
    model_profile: str = ""


class ThumbnailPromptBuilder:
    """Compose prompts through Prompt Intelligence (blocks + model profile)."""

    def __init__(
        self,
        *,
        intelligence: PromptIntelligenceEngine | None = None,
        profile_loader: ModelProfileLoader | None = None,
        model_name: str = "",
    ) -> None:
        self._intelligence = intelligence or PromptIntelligenceEngine(
            profile_loader=profile_loader
        )
        self._model_name = model_name
        self._last_primary: BuiltPrompt | None = None

    @property
    def last_primary(self) -> BuiltPrompt | None:
        return self._last_primary

    def build_variants(
        self,
        *,
        strategy: ThumbnailStrategy,
        hero_subject: str,
        composition: CompositionPlan,
        style: ChannelThumbnailStyle,
        dna: ChannelDNA,
        anti_ai: AntiAiRules,
        model_name: str = "",
    ) -> list[ThumbnailPromptPlan]:
        hero = (hero_subject or strategy.hero_subject or "").strip()
        if not hero:
            raise ValueError("Hero subject is required to build thumbnail prompts.")

        resolved_model = (model_name or self._model_name or "").strip()
        plans: list[ThumbnailPromptPlan] = []
        primary: BuiltPrompt | None = None
        for variant_id, variant_key, mood in THUMBNAIL_VARIANTS:
            built = self._intelligence.build(
                strategy=strategy,
                hero_subject=hero,
                composition=composition,
                style=style,
                dna=dna,
                anti_ai=anti_ai,
                variant_mood=mood,
                model_name=resolved_model,
            )
            if primary is None:
                primary = built
            plans.append(
                ThumbnailPromptPlan(
                    variant_id=variant_id,
                    variant_key=variant_key,
                    variant_label=variant_key.title(),
                    prompt=built.prompt,
                    negative_prompt=built.negative_prompt,
                    blocks=built.blocks.to_dict(),
                    prompt_quality=built.quality.to_report(),
                    model_profile=built.profile.display_name,
                )
            )
        self._last_primary = primary
        return plans

    def primary_prompt_text(self, plans: list[ThumbnailPromptPlan]) -> str:
        if not plans:
            return ""
        return plans[0].prompt

    def primary_prompt_quality(self) -> PromptQualityScore | None:
        if self._last_primary is None:
            return None
        return self._last_primary.quality
