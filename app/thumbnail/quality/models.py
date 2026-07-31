"""Quality Assurance models — scores, evaluation context, history entries.

Independent of any specific evaluator implementation so Vision AI can plug in later.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_QUALITY_THRESHOLD = 80
DEFAULT_MAX_QUALITY_ATTEMPTS = 3


@dataclass(frozen=True)
class ThumbnailQualityScore:
    """0–10 axes summing to a 0–100 total."""

    hero_subject: int = 0
    curiosity: int = 0
    composition: int = 0
    headline_space: int = 0
    impact: int = 0
    readability: int = 0
    dna: int = 0
    ctr: int = 0
    simplicity: int = 0
    professional: int = 0
    notes: str = ""
    evaluator_id: str = ""

    @property
    def score(self) -> int:
        total = (
            self.hero_subject
            + self.curiosity
            + self.composition
            + self.headline_space
            + self.impact
            + self.readability
            + self.dna
            + self.ctr
            + self.simplicity
            + self.professional
        )
        return max(0, min(100, int(total)))

    def with_clamped_axes(self) -> ThumbnailQualityScore:
        def clamp(value: int) -> int:
            try:
                return max(0, min(10, int(value)))
            except (TypeError, ValueError):
                return 0

        return ThumbnailQualityScore(
            hero_subject=clamp(self.hero_subject),
            curiosity=clamp(self.curiosity),
            composition=clamp(self.composition),
            headline_space=clamp(self.headline_space),
            impact=clamp(self.impact),
            readability=clamp(self.readability),
            dna=clamp(self.dna),
            ctr=clamp(self.ctr),
            simplicity=clamp(self.simplicity),
            professional=clamp(self.professional),
            notes=self.notes,
            evaluator_id=self.evaluator_id,
        )

    def to_report(self, *, approved: bool) -> dict[str, Any]:
        clamped = self.with_clamped_axes()
        return {
            "score": clamped.score,
            "hero_subject": clamped.hero_subject,
            "curiosity": clamped.curiosity,
            "composition": clamped.composition,
            "headline_space": clamped.headline_space,
            "impact": clamped.impact,
            "readability": clamped.readability,
            "dna": clamped.dna,
            "ctr": clamped.ctr,
            "simplicity": clamped.simplicity,
            "professional": clamped.professional,
            "approved": bool(approved),
            "notes": clamped.notes,
            "evaluator_id": clamped.evaluator_id,
        }


@dataclass(frozen=True)
class QualityEvaluationContext:
    """Everything an evaluator may use — including image bytes for Vision AI."""

    image_png: bytes
    prompt: str
    negative_prompt: str = ""
    hero_subject: str = ""
    hook: str = ""
    emotion: str = ""
    click_reason: str = ""
    channel_name: str = ""
    channel_dna: dict[str, Any] = field(default_factory=dict)
    composition: dict[str, Any] = field(default_factory=dict)
    critique: dict[str, Any] = field(default_factory=dict)
    variant_id: str = ""
    variant_key: str = ""
    seed: int = -1
    model: str = ""
    loras: tuple[str, ...] = ()
    attempt: int = 1
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityHistoryEntry:
    """One generation attempt recorded for learning / audit."""

    attempt: int
    score: int
    approved: bool
    date: str
    channel: str
    hero_subject: str
    hook: str
    prompt: str
    seed: int
    model: str
    rejection_reason: str = ""
    variant_id: str = ""
    quality: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityHistoryEntry:
        raw = dict(data or {})
        return cls(
            attempt=int(raw.get("attempt") or 0),
            score=int(raw.get("score") or 0),
            approved=bool(raw.get("approved")),
            date=str(raw.get("date") or ""),
            channel=str(raw.get("channel") or ""),
            hero_subject=str(raw.get("hero_subject") or ""),
            hook=str(raw.get("hook") or ""),
            prompt=str(raw.get("prompt") or ""),
            seed=int(raw.get("seed") if raw.get("seed") is not None else -1),
            model=str(raw.get("model") or ""),
            rejection_reason=str(raw.get("rejection_reason") or raw.get("waarom_afgekeurd") or ""),
            variant_id=str(raw.get("variant_id") or ""),
            quality=dict(raw.get("quality") or {}),
            extras=dict(raw.get("extras") or {}),
        )


@dataclass
class ThumbnailQualityHistory:
    """Append-only history of QA attempts for one project."""

    version: int = 1
    entries: list[QualityHistoryEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def read_json(cls, path: Path) -> ThumbnailQualityHistory:
        if not path.is_file():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return cls()
        entries_raw = raw.get("entries") if isinstance(raw.get("entries"), list) else []
        entries = [
            QualityHistoryEntry.from_dict(item)
            for item in entries_raw
            if isinstance(item, dict)
        ]
        return cls(version=int(raw.get("version") or 1), entries=entries)

    def append(self, entry: QualityHistoryEntry) -> None:
        if not entry.date:
            entry.date = datetime.now(timezone.utc).isoformat()
        self.entries.append(entry)


def write_quality_report(path: Path, score: ThumbnailQualityScore, *, approved: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(score.to_report(approved=approved), indent=2) + "\n",
        encoding="utf-8",
    )
