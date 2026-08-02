"""Thumbnail Intelligence 1.0 — think → plan → style → brand → prompt.

Does not generate images. ThumbnailService / Forge remain the image backends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.thumbnail.intelligence.branding import LogoPlacement, ThumbnailBrandingService
    from app.thumbnail.intelligence.consistency import ThumbnailConsistencyScore
    from app.thumbnail.intelligence.context import ThumbnailIntelligenceContext
    from app.thumbnail.intelligence.planner import ThumbnailPlan, ThumbnailPlanner
    from app.thumbnail.intelligence.prompt_builder import (
        BuiltThumbnailPrompt,
        ThumbnailIntelligencePromptBuilder,
    )
    from app.thumbnail.intelligence.service import (
        ThumbnailIntelligenceResult,
        ThumbnailIntelligenceService,
    )
    from app.thumbnail.intelligence.settings import ThumbnailStudioSettings

__all__ = [
    "BuiltThumbnailPrompt",
    "LogoPlacement",
    "ThumbnailBrandingService",
    "ThumbnailConsistencyScore",
    "ThumbnailIntelligenceContext",
    "ThumbnailIntelligencePromptBuilder",
    "ThumbnailIntelligenceResult",
    "ThumbnailIntelligenceService",
    "ThumbnailPlan",
    "ThumbnailPlanner",
    "ThumbnailStudioSettings",
]


def __getattr__(name: str):
    if name in {
        "LogoPlacement",
        "ThumbnailBrandingService",
    }:
        from app.thumbnail.intelligence import branding as mod

        return getattr(mod, name)
    if name in {"ThumbnailConsistencyScore", "score_thumbnail_consistency"}:
        from app.thumbnail.intelligence import consistency as mod

        return getattr(mod, name)
    if name in {"ThumbnailIntelligenceContext", "load_intelligence_context"}:
        from app.thumbnail.intelligence import context as mod

        return getattr(mod, name)
    if name in {"ThumbnailPlan", "ThumbnailPlanner"}:
        from app.thumbnail.intelligence import planner as mod

        return getattr(mod, name)
    if name in {"BuiltThumbnailPrompt", "ThumbnailIntelligencePromptBuilder"}:
        from app.thumbnail.intelligence import prompt_builder as mod

        return getattr(mod, name)
    if name in {"ThumbnailIntelligenceResult", "ThumbnailIntelligenceService"}:
        from app.thumbnail.intelligence import service as mod

        return getattr(mod, name)
    if name in {"ThumbnailStudioSettings", "ThumbnailStudioSettingsStore"}:
        from app.thumbnail.intelligence import settings as mod

        return getattr(mod, name)
    raise AttributeError(name)
