"""CriticReport — full evaluation result for Learning Engine later."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.creative.critic.rules import CriticFinding
from app.creative.critic.score import CriticScore


@dataclass
class CriticReport:
    """Immutable-ish evaluation snapshot (mutable for convenience before save)."""

    channel: str
    domain: str
    generator: str = ""
    project: str = ""
    date: str = ""
    score: CriticScore = field(default_factory=CriticScore)
    minimum_score: float = 90.0
    status: str = "Rejected"  # Approved | Rejected
    problems: list[str] = field(default_factory=list)
    findings: list[CriticFinding] = field(default_factory=list)
    consistency: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.date:
            self.date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.refresh_status()

    @property
    def approved(self) -> bool:
        return self.status.casefold() == "approved"

    def refresh_status(self) -> str:
        overall = float(self.score.overall)
        self.status = "Approved" if overall >= float(self.minimum_score) else "Rejected"
        return self.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "domain": self.domain,
            "generator": self.generator,
            "project": self.project,
            "date": self.date,
            "score": self.score.to_dict(),
            "minimum_score": self.minimum_score,
            "status": self.status,
            "approved": self.approved,
            "problems": list(self.problems),
            "findings": [f.to_dict() for f in self.findings],
            "consistency": dict(self.consistency),
            "notes": list(self.notes),
            "extras": dict(self.extras),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CriticReport:
        raw = dict(data or {})
        findings_raw = raw.get("findings") if isinstance(raw.get("findings"), list) else []
        findings = [
            CriticFinding(
                code=str(item.get("code") or ""),
                message=str(item.get("message") or ""),
                dimension=str(item.get("dimension") or "quality"),
                severity=float(item.get("severity") or 1.0),
            )
            for item in findings_raw
            if isinstance(item, dict)
        ]
        report = cls(
            channel=str(raw.get("channel") or ""),
            domain=str(raw.get("domain") or ""),
            generator=str(raw.get("generator") or ""),
            project=str(raw.get("project") or ""),
            date=str(raw.get("date") or ""),
            score=CriticScore.from_dict(
                raw.get("score") if isinstance(raw.get("score"), dict) else {}
            ),
            minimum_score=float(raw.get("minimum_score") or 90.0),
            status=str(raw.get("status") or "Rejected"),
            problems=[str(p) for p in (raw.get("problems") or [])],
            findings=findings,
            consistency=dict(raw.get("consistency") or {})
            if isinstance(raw.get("consistency"), dict)
            else {},
            notes=[str(n) for n in (raw.get("notes") or [])],
            extras=dict(raw.get("extras") or {})
            if isinstance(raw.get("extras"), dict)
            else {},
        )
        report.refresh_status()
        return report
