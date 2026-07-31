"""Abstract QualityEvaluator — swap Rule-Based ↔ Vision AI without touching the service."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.thumbnail.quality.models import QualityEvaluationContext, ThumbnailQualityScore


class QualityEvaluator(ABC):
    """Score a thumbnail candidate.

    Implementations must not assume they can only read prompts — Vision models
    will inspect ``context.image_png``. The Quality Assurance Engine depends
    only on this interface.
    """

    @property
    @abstractmethod
    def evaluator_id(self) -> str:
        """Stable id (e.g. ``rules_v1``, ``gpt_vision``, ``gemini_vision``)."""

    @abstractmethod
    def evaluate(self, context: QualityEvaluationContext) -> ThumbnailQualityScore:
        """Return axis scores 0–10. Total is derived as the sum (0–100)."""
