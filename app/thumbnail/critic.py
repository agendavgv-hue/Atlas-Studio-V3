"""Future AI Thumbnail Critic — select the best of four generated variants.

Current default: ``PrimaryVariantCritic`` (settings.primary_variant).
Swap in a vision-capable critic later without changing the service flow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ThumbnailCandidate:
    """One generated thumbnail offered to the critic."""

    variant_id: str
    variant_key: str
    image_png: bytes
    prompt: str = ""
    file_name: str = ""
    seed: int = -1
    model: str = ""


@dataclass(frozen=True)
class ThumbnailCriticScores:
    """Score axes reserved for the future vision critic."""

    curiosity: float = 0.0
    simplicity: float = 0.0
    composition: float = 0.0
    readability: float = 0.0
    emotional_impact: float = 0.0
    ctr_potential: float = 0.0
    overall: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ThumbnailCriticResult:
    """Winner + optional per-variant scores."""

    winner_variant_id: str
    selection_method: str
    rationale: str = ""
    scores: dict[str, ThumbnailCriticScores] = field(default_factory=dict)
    deferred: bool = False

    def to_dict(self) -> dict:
        return {
            "winner_variant_id": self.winner_variant_id,
            "selection_method": self.selection_method,
            "rationale": self.rationale,
            "deferred": self.deferred,
            "scores": {key: value.to_dict() for key, value in self.scores.items()},
        }


class ThumbnailCritic(Protocol):
    """Protocol for present and future thumbnail selectors."""

    def select(self, candidates: list[ThumbnailCandidate]) -> ThumbnailCriticResult:
        """Choose the primary thumbnail from generated candidates."""


class PrimaryVariantCritic:
    """Default critic — honors ``settings.primary_variant`` until AI critic ships."""

    def __init__(self, primary_variant_id: str = "A") -> None:
        self._primary = (primary_variant_id or "A").strip().upper() or "A"

    def select(self, candidates: list[ThumbnailCandidate]) -> ThumbnailCriticResult:
        if not candidates:
            raise ValueError("Thumbnail critic requires at least one candidate.")
        by_id = {item.variant_id.upper(): item for item in candidates}
        winner = by_id.get(self._primary) or candidates[0]
        return ThumbnailCriticResult(
            winner_variant_id=winner.variant_id,
            selection_method="settings_primary",
            rationale=(
                f"Primary variant {winner.variant_id} selected by settings "
                "(AI Thumbnail Critic not enabled yet)."
            ),
            deferred=True,
            scores={},
        )
