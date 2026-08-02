"""Design Engine V1 — Atlas as graphic designer after AI illustration."""

from __future__ import annotations

from typing import Any

from app.thumbnail.design_engine.models import (
    DesignReviewBoard,
    DesignScores,
    LayoutCandidate,
    SceneMap,
)
from app.thumbnail.design_engine.service import DesignEngineResult, DesignEngineService
from app.thumbnail.design_engine.store import (
    DESIGN_REVIEW_BASENAME,
    design_review_path,
    read_design_review,
    write_design_review,
)
from app.thumbnail.design_engine.typography import best_line_break, invent_line_breaks

__all__ = [
    "DESIGN_REVIEW_BASENAME",
    "DesignEngineResult",
    "DesignEngineService",
    "DesignReviewBoard",
    "DesignScores",
    "LayoutCandidate",
    "SceneMap",
    "best_line_break",
    "design_review_path",
    "invent_line_breaks",
    "read_design_review",
    "write_design_review",
]


def __getattr__(name: str) -> Any:
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
