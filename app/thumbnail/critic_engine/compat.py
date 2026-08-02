"""Adapter: CriticReport → legacy ThumbnailCriticScores for pipeline debug."""

from __future__ import annotations

from app.thumbnail.critic_engine.models import CriticReport
from app.thumbnail.pipeline.critic_scores import ThumbnailCriticScores


def report_to_pipeline_scores(report: CriticReport) -> ThumbnailCriticScores:
    by = report.axis_map()

    def _s(name: str, fallback: float = 0.0) -> float:
        axis = by.get(name)
        return float(axis.score) if axis else fallback

    adjustments = [a.improvement for a in report.weak_axes()[:6]]
    return ThumbnailCriticScores(
        brand_consistency=_s("brand_consistency"),
        reference_similarity=_s("reference_similarity"),
        readability=_s("text_layout", _s("headline_size")),
        composition=_s("composition"),
        ctr_potential=_s("ctr_potential"),
        mystery=_s("mystery"),
        visual_impact=_s("overall_impact", _s("professional_appearance")),
        overall=float(report.overall),
        approved=bool(report.approved),
        threshold=int(report.threshold),
        notes=list(report.notes),
        adjustments=adjustments,
    )
