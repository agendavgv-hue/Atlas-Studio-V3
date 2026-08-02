"""CriticScore — multi-dimension quality scores (0–100)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CriticScore:
    """Dimension scores for one Critic evaluation."""

    overall: float = 0.0
    brand: float = 100.0
    style: float = 100.0
    quality: float = 100.0
    readability: float = 100.0
    creativity: float = 100.0
    technical: float = 100.0
    composition: float = 100.0
    identity: float = 100.0
    extras: dict[str, float] = field(default_factory=dict)

    def clamp(self) -> CriticScore:
        dims = (
            "overall",
            "brand",
            "style",
            "quality",
            "readability",
            "creativity",
            "technical",
            "composition",
            "identity",
        )
        for name in dims:
            value = float(getattr(self, name))
            setattr(self, name, max(0.0, min(100.0, value)))
        self.extras = {
            k: max(0.0, min(100.0, float(v))) for k, v in (self.extras or {}).items()
        }
        return self

    def recompute_overall(self, *, weights: dict[str, float] | None = None) -> float:
        """Weighted mean of dimensions → overall (excludes overall itself)."""
        default = {
            "brand": 1.2,
            "style": 1.2,
            "quality": 1.0,
            "readability": 0.8,
            "creativity": 0.7,
            "technical": 0.8,
            "composition": 1.1,
            "identity": 1.4,
        }
        w = dict(default)
        if weights:
            w.update(weights)
        total_w = 0.0
        total = 0.0
        for name, weight in w.items():
            if weight <= 0:
                continue
            if name in self.extras:
                value = float(self.extras[name])
            else:
                value = float(getattr(self, name, 100.0))
            total += value * weight
            total_w += weight
        self.overall = round(total / total_w, 2) if total_w else 0.0
        return self.overall

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["overall"] = round(float(self.overall), 2)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CriticScore:
        raw = dict(data or {})
        extras = raw.get("extras") if isinstance(raw.get("extras"), dict) else {}
        score = cls(
            overall=_f(raw.get("overall"), 0.0),
            brand=_f(raw.get("brand"), 100.0),
            style=_f(raw.get("style"), 100.0),
            quality=_f(raw.get("quality"), 100.0),
            readability=_f(raw.get("readability"), 100.0),
            creativity=_f(raw.get("creativity"), 100.0),
            technical=_f(raw.get("technical"), 100.0),
            composition=_f(raw.get("composition"), 100.0),
            identity=_f(raw.get("identity"), 100.0),
            extras={str(k): _f(v, 100.0) for k, v in extras.items()},
        )
        return score.clamp()


def _f(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
