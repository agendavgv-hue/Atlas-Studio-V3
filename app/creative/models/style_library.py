"""Style Library — extensible weighted style profile for a channel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.creative.models._util import from_dict, to_dict


@dataclass
class StyleLibrary:
    """Numeric weights (0–100) plus free-form style descriptors.

    Unknown future keys live in ``extras`` so the schema stays open.
    """

    realism: float = 90.0
    mystery: float = 50.0
    fantasy: float = 5.0
    documentary: float = 70.0
    darkness: float = 60.0
    fog: float = 20.0
    contrast: float = 85.0
    color_palette: str = ""
    camera_style: str = ""
    animation_style: str = ""
    movie_pacing: str = ""
    thumbnail_style: str = ""
    story_style: str = ""
    voice_style: str = ""
    music_style: str = ""
    lighting: str = ""
    depth: str = ""
    image_quality: str = "ultra"
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> StyleLibrary:
        raw = dict(data or {})
        # Promote unknown top-level keys into extras for forward compatibility.
        known = {f.name for f in StyleLibrary.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        extras = dict(raw.get("extras") or {}) if isinstance(raw.get("extras"), dict) else {}
        for key, value in raw.items():
            if key not in known and key != "extras":
                extras[key] = value
        raw["extras"] = extras
        # Coerce weight fields
        for key in (
            "realism",
            "mystery",
            "fantasy",
            "documentary",
            "darkness",
            "fog",
            "contrast",
        ):
            if key in raw:
                try:
                    raw[key] = float(raw[key])
                except (TypeError, ValueError):
                    raw.pop(key, None)
        return from_dict(cls, raw)

    def set_weight(self, name: str, value: float) -> None:
        if hasattr(self, name) and name in {
            "realism",
            "mystery",
            "fantasy",
            "documentary",
            "darkness",
            "fog",
            "contrast",
        }:
            setattr(self, name, max(0.0, min(100.0, float(value))))
        else:
            self.extras[name] = max(0.0, min(100.0, float(value)))
