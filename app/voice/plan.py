"""VoicePlan — planner output before the durable VoiceManifest is built."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class VoiceSegment:
    """One narration segment. Sprint 11 often uses a single full-script segment."""

    index: int  # 1-based
    text: str
    pause_after_sec: float = 0.0  # reserved
    emphasis: str = ""  # reserved
    emotion: str = ""  # reserved
    speaker: str = ""  # reserved
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceSegment:
        raw = dict(data or {})
        return cls(
            index=int(raw.get("index") or 0),
            text=str(raw.get("text") or ""),
            pause_after_sec=float(raw.get("pause_after_sec") or 0.0),
            emphasis=str(raw.get("emphasis") or ""),
            emotion=str(raw.get("emotion") or ""),
            speaker=str(raw.get("speaker") or ""),
            extras=dict(raw.get("extras") or {}),
        )


@dataclass(frozen=True)
class VoicePlan:
    """Immutable planner result — segments only; Generator reads the Manifest."""

    segments: tuple[VoiceSegment, ...]
    language: str = "en-US"
    estimated_duration_sec: float | None = None
    rationale: str = ""

    @property
    def count(self) -> int:
        return len(self.segments)

    @property
    def full_text(self) -> str:
        return "\n\n".join(segment.text.strip() for segment in self.segments if segment.text.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": [segment.to_dict() for segment in self.segments],
            "language": self.language,
            "estimated_duration_sec": self.estimated_duration_sec,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoicePlan:
        raw = dict(data or {})
        segments = tuple(
            VoiceSegment.from_dict(item)
            for item in (raw.get("segments") or [])
            if isinstance(item, dict)
        )
        estimated = raw.get("estimated_duration_sec")
        try:
            estimated_duration = float(estimated) if estimated is not None else None
        except (TypeError, ValueError):
            estimated_duration = None
        return cls(
            segments=segments,
            language=str(raw.get("language") or "en-US"),
            estimated_duration_sec=estimated_duration,
            rationale=str(raw.get("rationale") or ""),
        )
