"""Public exports for Thumbnail Critic & Improve Engine."""

from __future__ import annotations

from typing import Any

from app.thumbnail.critic_engine.improve import ImproveEngine
from app.thumbnail.critic_engine.learning import CriticLearningStore, CriticMemory
from app.thumbnail.critic_engine.models import (
    AXIS_LABELS,
    CRITIC_AXES,
    AxisCritique,
    CriticGroupScores,
    CriticReport,
    ImproveAction,
    ImprovePlan,
    ReviewVersion,
    ThumbnailReviewBoard,
)
from app.thumbnail.critic_engine.service import (
    DEFAULT_CRITIC_THRESHOLD,
    ThumbnailCriticService,
)
from app.thumbnail.critic_engine.store import (
    THUMBNAIL_CRITIC_REPORT_BASENAME,
    THUMBNAIL_REVIEW_BASENAME,
    read_review_board,
    write_critic_report,
    write_review_board,
)

__all__ = [
    "AXIS_LABELS",
    "CRITIC_AXES",
    "DEFAULT_CRITIC_THRESHOLD",
    "AxisCritique",
    "CriticGroupScores",
    "CriticLearningStore",
    "CriticMemory",
    "CriticReport",
    "ImproveAction",
    "ImproveEngine",
    "ImprovePlan",
    "ReviewVersion",
    "THUMBNAIL_CRITIC_REPORT_BASENAME",
    "THUMBNAIL_REVIEW_BASENAME",
    "ThumbnailCriticService",
    "ThumbnailReviewBoard",
    "read_review_board",
    "report_to_pipeline_scores",
    "write_critic_report",
    "write_review_board",
]


def __getattr__(name: str) -> Any:
    if name == "report_to_pipeline_scores":
        from app.thumbnail.critic_engine.compat import report_to_pipeline_scores

        return report_to_pipeline_scores
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
