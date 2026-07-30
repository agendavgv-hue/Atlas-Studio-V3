"""VoiceManifest — durable production plan for one voice run.

Written as ``voice/voice_manifest.json`` beside ``voice.wav``.
VoiceGenerator consumes this manifest; it does not invent structure.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.voice.naming import VOICE_BASENAME, VOICE_FOLDER
from app.voice.plan import VoicePlan, VoiceSegment


MANIFEST_VERSION = 1


@dataclass
class VoiceOutputPlan:
    """Where narration lands. Sprint 11 exports WAV only."""

    folder: str = VOICE_FOLDER
    filename: str = VOICE_BASENAME


@dataclass
class VoiceManifest:
    """Complete durable plan for one narration export."""

    version: int = MANIFEST_VERSION
    provider_id: str = ""
    voice_id: str = ""
    voice_name: str = ""
    language: str = "en-US"
    model: str = ""
    speed: float = 1.0
    pitch: float = 0.0  # reserved
    stability: float = 0.0
    style: float = 0.0
    similarity: float = 0.0
    segments: list[VoiceSegment] = field(default_factory=list)
    output: VoiceOutputPlan = field(default_factory=VoiceOutputPlan)
    estimated_duration_sec: float | None = None
    duration_sec: float | None = None  # filled after export when known
    rationale: str = ""
    exported: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            segment.text.strip() for segment in self.segments if segment.text.strip()
        )

    @classmethod
    def from_plan(
        cls,
        plan: VoicePlan,
        *,
        provider_id: str = "",
        voice_id: str = "",
        voice_name: str = "",
        model: str = "",
        speed: float = 1.0,
        pitch: float = 0.0,
        stability: float = 0.0,
        style: float = 0.0,
        similarity: float = 0.0,
    ) -> VoiceManifest:
        return cls(
            provider_id=provider_id,
            voice_id=voice_id,
            voice_name=voice_name,
            language=plan.language,
            model=model,
            speed=speed,
            pitch=pitch,
            stability=stability,
            style=style,
            similarity=similarity,
            segments=list(plan.segments),
            estimated_duration_sec=plan.estimated_duration_sec,
            rationale=plan.rationale,
            exported=False,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceManifest:
        raw = dict(data or {})
        output_raw = raw.get("output") if isinstance(raw.get("output"), dict) else {}
        segments = [
            VoiceSegment.from_dict(item)
            for item in (raw.get("segments") or [])
            if isinstance(item, dict)
        ]

        def _opt_float(key: str) -> float | None:
            value = raw.get(key)
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        return cls(
            version=int(raw.get("version") or MANIFEST_VERSION),
            provider_id=str(raw.get("provider_id") or ""),
            voice_id=str(raw.get("voice_id") or ""),
            voice_name=str(raw.get("voice_name") or ""),
            language=str(raw.get("language") or "en-US"),
            model=str(raw.get("model") or ""),
            speed=float(raw.get("speed") or 1.0),
            pitch=float(raw.get("pitch") or 0.0),
            stability=float(raw.get("stability") or 0.0),
            style=float(raw.get("style") or 0.0),
            similarity=float(raw.get("similarity") or 0.0),
            segments=segments,
            output=VoiceOutputPlan(
                folder=str(output_raw.get("folder") or VOICE_FOLDER),
                filename=str(output_raw.get("filename") or VOICE_BASENAME),
            ),
            estimated_duration_sec=_opt_float("estimated_duration_sec"),
            duration_sec=_opt_float("duration_sec"),
            rationale=str(raw.get("rationale") or ""),
            exported=bool(raw.get("exported", False)),
            extras=dict(raw.get("extras") or {}),
        )

    @classmethod
    def read_json(cls, path: Path) -> VoiceManifest:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
