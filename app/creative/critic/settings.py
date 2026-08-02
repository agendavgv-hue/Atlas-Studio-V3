"""Per-channel Critic thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CriticSettings:
    minimum_score: float = 90.0
    persist_reports: bool = True
    max_reports: int = 200

    def to_dict(self) -> dict[str, Any]:
        return {
            "minimum_score": self.minimum_score,
            "persist_reports": self.persist_reports,
            "max_reports": self.max_reports,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CriticSettings:
        raw = dict(data or {})
        try:
            minimum = float(raw.get("minimum_score", 90.0))
        except (TypeError, ValueError):
            minimum = 90.0
        try:
            max_reports = int(raw.get("max_reports", 200))
        except (TypeError, ValueError):
            max_reports = 200
        return cls(
            minimum_score=max(0.0, min(100.0, minimum)),
            persist_reports=bool(raw.get("persist_reports", True)),
            max_reports=max(1, max_reports),
        )
