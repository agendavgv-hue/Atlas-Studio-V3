"""ThumbnailCriticService — professional multi-axis thumbnail review."""

from __future__ import annotations

from app.creative.engine.brief import CreativeBrief
from app.thumbnail.critic_engine.models import (
    GROUP_AXES,
    CriticGroupScores,
    CriticReport,
)
from app.thumbnail.critic_engine.scoring import score_all_axes
from app.thumbnail.pipeline.plan import ThumbnailPlan
from app.thumbnail.pipeline.reference_compare import ReferenceSimilarityReport
from app.thumbnail.scene_director.models import SceneBlueprint
from app.thumbnail.style_dna.models import ThumbnailStyleDNA

DEFAULT_CRITIC_THRESHOLD = 90


class ThumbnailCriticService:
    """Score a finished thumbnail like a YouTube thumbnail designer."""

    def __init__(self, threshold: int = DEFAULT_CRITIC_THRESHOLD) -> None:
        self.threshold = max(1, min(100, int(threshold)))

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
        composed: bool = True,
        scene_blueprint: SceneBlueprint | None = None,
        style_dna: ThumbnailStyleDNA | None = None,
        assets=None,
        attempt: int = 1,
    ) -> CriticReport:
        axes = score_all_axes(
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
        )
        by_name = {a.axis: a.score for a in axes}

        def _avg(keys: tuple[str, ...]) -> float:
            vals = [by_name[k] for k in keys if k in by_name]
            return round(sum(vals) / max(1, len(vals)), 2)

        groups = CriticGroupScores(
            story=_avg(GROUP_AXES["story"]),
            brand=_avg(GROUP_AXES["brand"]),
            layout=_avg(GROUP_AXES["layout"]),
            composition=_avg(GROUP_AXES["composition"]),
            ctr=_avg(GROUP_AXES["ctr"]),
            curiosity=float(by_name.get("curiosity") or 0.0),
            overall=round(sum(a.score for a in axes) / max(1, len(axes)), 2),
        )
        overall = groups.overall
        approved = overall >= self.threshold
        notes = [f"{a.label}: {a.why}" for a in axes if a.score < self.threshold][:8]
        return CriticReport(
            axes=axes,
            groups=groups,
            overall=overall,
            approved=approved,
            threshold=self.threshold,
            attempt=attempt,
            channel_name=brief.channel_name,
            notes=notes,
            extras={
                "hook": hook,
                "reference_count": similarity.reference_count,
                "has_logo": has_logo,
                "has_frame": has_frame,
            },
        )
