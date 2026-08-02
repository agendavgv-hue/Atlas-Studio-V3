"""Thumbnail Critic V3 — thin adapter over ThumbnailCriticService."""

from __future__ import annotations

from app.creative.engine.brief import CreativeBrief
from app.thumbnail.critic_engine.compat import report_to_pipeline_scores
from app.thumbnail.critic_engine.service import ThumbnailCriticService
from app.thumbnail.pipeline.critic_scores import (
    DEFAULT_CRITIC_THRESHOLD,
    ThumbnailCriticScores,
)
from app.thumbnail.pipeline.plan import ThumbnailPlan
from app.thumbnail.pipeline.reference_compare import ReferenceSimilarityReport

__all__ = [
    "DEFAULT_CRITIC_THRESHOLD",
    "ThumbnailCriticScores",
    "ThumbnailPipelineCritic",
]


class ThumbnailPipelineCritic:
    """Backward-compatible wrapper around ThumbnailCriticService."""

    def __init__(self, threshold: int = DEFAULT_CRITIC_THRESHOLD) -> None:
        self.threshold = max(1, min(100, int(threshold)))
        self._service = ThumbnailCriticService(threshold=self.threshold)

    def evaluate(
        self,
        *,
        brief: CreativeBrief,
        plan: ThumbnailPlan,
        similarity: ReferenceSimilarityReport,
        hook: str,
        prompt: str,
        has_logo: bool,
        has_frame: bool,
        composed: bool,
        scene_blueprint=None,
        style_dna=None,
        assets=None,
        attempt: int = 1,
    ) -> ThumbnailCriticScores:
        report = self._service.evaluate(
            brief=brief,
            plan=plan,
            similarity=similarity,
            hook=hook,
            prompt=prompt,
            has_logo=has_logo,
            has_frame=has_frame,
            composed=composed,
            scene_blueprint=scene_blueprint,
            style_dna=style_dna,
            assets=assets,
            attempt=attempt,
        )
        return report_to_pipeline_scores(report)
