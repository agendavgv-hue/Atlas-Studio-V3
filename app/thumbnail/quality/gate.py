"""QualityGate — approve / reject against a threshold using any QualityEvaluator."""

from __future__ import annotations

from dataclasses import dataclass

from app.thumbnail.quality.evaluator import QualityEvaluator
from app.thumbnail.quality.models import (
    DEFAULT_QUALITY_THRESHOLD,
    QualityEvaluationContext,
    ThumbnailQualityScore,
)
from app.thumbnail.quality.rule_evaluator import RuleBasedQualityEvaluator


@dataclass(frozen=True)
class QualityGateResult:
    """Outcome of scoring one candidate against the acceptance threshold."""

    score: ThumbnailQualityScore
    approved: bool
    threshold: int
    rejection_reason: str = ""

    @property
    def total(self) -> int:
        return self.score.score

    def to_report(self) -> dict:
        report = self.score.to_report(approved=self.approved)
        report["threshold"] = self.threshold
        if self.rejection_reason:
            report["rejection_reason"] = self.rejection_reason
        return report


class QualityGate:
    """Accept thumbnails only when the evaluator score meets the threshold."""

    def __init__(
        self,
        evaluator: QualityEvaluator | None = None,
        *,
        threshold: int = DEFAULT_QUALITY_THRESHOLD,
    ) -> None:
        self._evaluator = evaluator or RuleBasedQualityEvaluator()
        self._threshold = max(0, min(100, int(threshold)))

    @property
    def evaluator(self) -> QualityEvaluator:
        return self._evaluator

    @property
    def threshold(self) -> int:
        return self._threshold

    def assess(self, context: QualityEvaluationContext) -> QualityGateResult:
        score = self._evaluator.evaluate(context).with_clamped_axes()
        approved = score.score >= self._threshold
        reason = ""
        if not approved:
            reason = (
                f"Score {score.score} below threshold {self._threshold}"
                + (f" — {score.notes}" if score.notes else "")
            )
        return QualityGateResult(
            score=score,
            approved=approved,
            threshold=self._threshold,
            rejection_reason=reason,
        )

    def pick_best_approved(
        self,
        contexts: list[QualityEvaluationContext],
    ) -> tuple[QualityGateResult, QualityEvaluationContext] | None:
        """Return the highest-scoring approved candidate, if any."""
        best: tuple[QualityGateResult, QualityEvaluationContext] | None = None
        for context in contexts:
            result = self.assess(context)
            if not result.approved:
                continue
            if best is None or result.total > best[0].total:
                best = (result, context)
        return best

    def score_all(
        self,
        contexts: list[QualityEvaluationContext],
    ) -> list[tuple[QualityGateResult, QualityEvaluationContext]]:
        return [(self.assess(context), context) for context in contexts]
