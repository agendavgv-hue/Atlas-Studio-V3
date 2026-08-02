"""Legacy pipeline critic score payload (shared leaf module)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_CRITIC_THRESHOLD = 90


@dataclass
class ThumbnailCriticScores:
    brand_consistency: float = 0.0
    reference_similarity: float = 0.0
    readability: float = 0.0
    composition: float = 0.0
    ctr_potential: float = 0.0
    mystery: float = 0.0
    visual_impact: float = 0.0
    overall: float = 0.0
    approved: bool = False
    threshold: int = DEFAULT_CRITIC_THRESHOLD
    notes: list[str] = field(default_factory=list)
    adjustments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
