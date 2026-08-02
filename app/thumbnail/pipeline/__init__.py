"""Thumbnail Pipeline V3 — definitive production engine package."""

from __future__ import annotations

from typing import Any

__all__ = [
    "DEFAULT_CRITIC_THRESHOLD",
    "THUMBNAIL_DEBUG_BASENAME",
    "THUMBNAIL_PLAN_BASENAME",
    "ThumbnailCompositionPlanner",
    "ThumbnailCriticScores",
    "ThumbnailPlan",
    "ThumbnailPipelineEngine",
]


def __getattr__(name: str) -> Any:
    if name in {"DEFAULT_CRITIC_THRESHOLD", "ThumbnailCriticScores"}:
        from app.thumbnail.pipeline.critic_scores import (
            DEFAULT_CRITIC_THRESHOLD,
            ThumbnailCriticScores,
        )

        return {
            "DEFAULT_CRITIC_THRESHOLD": DEFAULT_CRITIC_THRESHOLD,
            "ThumbnailCriticScores": ThumbnailCriticScores,
        }[name]
    if name in {"THUMBNAIL_DEBUG_BASENAME", "THUMBNAIL_PLAN_BASENAME", "ThumbnailPipelineEngine"}:
        from app.thumbnail.pipeline import engine as mod

        return getattr(mod, name)
    if name in {"ThumbnailPlan", "ThumbnailCompositionPlanner"}:
        from app.thumbnail.pipeline import plan as mod

        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
