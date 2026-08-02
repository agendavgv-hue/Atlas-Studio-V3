"""ThumbnailIntelligenceService — plan → brand → prompt → consistency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.providers.base import TextProvider
from app.services.thumbnail_reference_service import ThumbnailReferenceService
from app.thumbnail.intelligence.branding import ThumbnailBrandingService
from app.thumbnail.intelligence.consistency import (
    ThumbnailConsistencyScore,
    score_thumbnail_consistency,
)
from app.thumbnail.intelligence.context import (
    ThumbnailIntelligenceContext,
    load_intelligence_context,
)
from app.thumbnail.intelligence.planner import ThumbnailPlan, ThumbnailPlanner
from app.thumbnail.intelligence.prompt_builder import (
    BuiltThumbnailPrompt,
    ThumbnailIntelligencePromptBuilder,
)
from app.thumbnail.intelligence.settings import (
    ThumbnailStudioSettings,
    ThumbnailStudioSettingsStore,
)


@dataclass
class ThumbnailIntelligenceResult:
    plan: ThumbnailPlan
    prompt: BuiltThumbnailPrompt
    consistency: ThumbnailConsistencyScore
    intelligence: ThumbnailIntelligenceContext

    def critic_payload(self, *, hook: str = "") -> dict[str, Any]:
        return self.intelligence.to_critic_payload(
            hook=hook,
            prompt=self.prompt.prompt,
        )


class ThumbnailIntelligenceService:
    """Entry point for Thumbnail Intelligence 1.0 (does not call the image model)."""

    def __init__(
        self,
        data_root: Path,
        *,
        text_provider: TextProvider | None = None,
    ) -> None:
        self._data_root = Path(data_root)
        self._text = text_provider
        self._settings = ThumbnailStudioSettingsStore(self._data_root)
        self._branding = ThumbnailBrandingService()
        self._prompts = ThumbnailIntelligencePromptBuilder(self._branding)

    def references(self, channel: str) -> ThumbnailReferenceService:
        return ThumbnailReferenceService(self._data_root, text_provider=self._text)

    def load_settings(self, channel: str) -> ThumbnailStudioSettings:
        return self._settings.load(channel)

    def save_settings(self, channel: str, settings: ThumbnailStudioSettings) -> Path:
        return self._settings.save(channel, settings)

    def load_context(self, channel: str) -> ThumbnailIntelligenceContext:
        return load_intelligence_context(
            self._data_root, channel, text_provider=self._text
        )

    def design(
        self,
        *,
        channel: str,
        script_text: str,
        sheet_text: str = "",
        channel_dna_text: str = "",
        hero_subject: str = "",
        hook: str = "",
    ) -> ThumbnailIntelligenceResult:
        if self._text is None:
            raise ValueError("text_provider required for ThumbnailPlanner")
        intelligence = self.load_context(channel)
        plan = ThumbnailPlanner(self._text).plan(
            script_text=script_text,
            sheet_text=sheet_text,
            channel_name=channel,
            channel_dna_text=channel_dna_text,
            intelligence=intelligence,
        )
        built = self._prompts.build(
            plan=plan,
            intelligence=intelligence,
            hero_subject=hero_subject or plan.strategy.hero_subject,
            hook=hook,
        )
        consistency = score_thumbnail_consistency(
            intelligence, prompt=built.prompt, hook=hook
        )
        return ThumbnailIntelligenceResult(
            plan=plan,
            prompt=built,
            consistency=consistency,
            intelligence=intelligence,
        )
