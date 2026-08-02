"""CriticRule — extensible evaluation checks (not generative prompts)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.creative.critic.domains import CriticDomain


@dataclass(frozen=True)
class CriticFinding:
    """One problem / improvement point from the Critic."""

    code: str
    message: str
    dimension: str = "quality"
    severity: float = 1.0  # multiplies score penalty

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "dimension": self.dimension,
            "severity": self.severity,
        }


@dataclass
class CriticRule:
    """A reusable critic check applied to a payload dict."""

    id: str
    title: str
    domain: str  # CriticDomain value or "*" for all
    dimension: str = "quality"
    description: str = ""
    enabled: bool = True
    weight: float = 1.0
    extras: dict[str, Any] = field(default_factory=dict)
    # Optional callable set at runtime; not serialized.
    check: Callable[[dict[str, Any], dict[str, Any]], list[CriticFinding]] | None = field(
        default=None, repr=False, compare=False
    )

    def applies_to(self, domain: CriticDomain | str) -> bool:
        if not self.enabled:
            return False
        key = domain.value if isinstance(domain, CriticDomain) else str(domain)
        key = key.casefold()
        target = (self.domain or "*").casefold()
        return target in {"*", "all"} or target == key

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "dimension": self.dimension,
            "description": self.description,
            "enabled": self.enabled,
            "weight": self.weight,
            "extras": dict(self.extras),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CriticRule:
        raw = dict(data or {})
        return cls(
            id=str(raw.get("id") or "").strip(),
            title=str(raw.get("title") or "").strip(),
            domain=str(raw.get("domain") or "*").strip() or "*",
            dimension=str(raw.get("dimension") or "quality").strip() or "quality",
            description=str(raw.get("description") or ""),
            enabled=bool(raw.get("enabled", True)),
            weight=float(raw.get("weight") or 1.0),
            extras=dict(raw.get("extras") or {})
            if isinstance(raw.get("extras"), dict)
            else {},
        )
