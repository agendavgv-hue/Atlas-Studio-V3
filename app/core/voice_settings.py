"""Voice-provider settings — all knobs configurable, none hardcoded in pipelines."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class VoiceSettings:
    """Persisted voice connection and synthesis parameters.

    Shared across Local Voice Engine and optional cloud providers.
    Unused fields for a given provider are simply ignored.
    """

    api_key: str = ""
    voice_id: str = "local_default"
    voice_name: str = "Default"
    language: str = "en-US"
    model: str = ""
    stability: float = 0.5
    style: float = 0.0
    speed: float = 1.0
    similarity: float = 0.75
    output_format: str = "mp3"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> VoiceSettings:
        raw = data or {}
        voice_id = str(raw.get("voice_id") or "local_default").strip() or "local_default"
        voice_name = str(raw.get("voice_name") or "").strip() or voice_id
        language = str(raw.get("language") or "en-US").strip() or "en-US"
        output_format = str(raw.get("output_format") or "mp3").strip() or "mp3"
        return cls(
            api_key=str(raw.get("api_key") or "").strip(),
            voice_id=voice_id,
            voice_name=voice_name,
            language=language,
            model=str(raw.get("model") or "").strip(),
            stability=_clamp(_as_float(raw.get("stability"), 0.5), 0.0, 1.0),
            style=_clamp(_as_float(raw.get("style"), 0.0), 0.0, 1.0),
            speed=_clamp(_as_float(raw.get("speed"), 1.0), 0.5, 2.0),
            similarity=_clamp(_as_float(raw.get("similarity"), 0.75), 0.0, 1.0),
            output_format=output_format,
        )


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
