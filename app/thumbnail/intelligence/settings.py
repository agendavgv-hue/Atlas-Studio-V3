"""Per-channel Thumbnail Studio settings (Creative Director knobs)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.channels.channel_ids import channel_id
from app.core.storage_paths import StoragePaths

LOGO_POSITIONS = (
    "auto",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "center",
)


@dataclass
class ThumbnailStudioSettings:
    """User-facing Thumbnail Intelligence controls per channel."""

    thumbnail_style: str = "cinematic"
    quality: str = "ultra"
    creativity: float = 60.0  # 0–100
    style_strength: float = 80.0
    brand_strength: float = 85.0
    logo_visible: bool = True
    logo_position: str = "auto"
    logo_size: float = 0.12  # fraction of frame
    logo_opacity: float = 0.92
    safe_margin_px: int = 48
    auto_scale_logo: bool = True
    max_words: int = 4
    negative_space: str = "left"
    contrast: str = "very_high"
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ThumbnailStudioSettings:
        raw = dict(data or {})
        extras = dict(raw.get("extras") or {}) if isinstance(raw.get("extras"), dict) else {}
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        for key, value in raw.items():
            if key not in known:
                extras[key] = value
        pos = str(raw.get("logo_position") or "auto").strip().casefold()
        if pos not in LOGO_POSITIONS:
            pos = "auto"
        return cls(
            thumbnail_style=str(raw.get("thumbnail_style") or "cinematic"),
            quality=str(raw.get("quality") or "ultra"),
            creativity=_clamp(raw.get("creativity"), 60.0),
            style_strength=_clamp(raw.get("style_strength"), 80.0),
            brand_strength=_clamp(raw.get("brand_strength"), 85.0),
            logo_visible=bool(raw.get("logo_visible", True)),
            logo_position=pos,
            logo_size=_clamp(raw.get("logo_size"), 0.12, 0.04, 0.35),
            logo_opacity=_clamp(raw.get("logo_opacity"), 0.92, 0.2, 1.0),
            safe_margin_px=int(raw.get("safe_margin_px") or 48),
            auto_scale_logo=bool(raw.get("auto_scale_logo", True)),
            max_words=max(1, min(8, int(raw.get("max_words") or 4))),
            negative_space=str(raw.get("negative_space") or "left"),
            contrast=str(raw.get("contrast") or "very_high"),
            extras=extras,
        )


class ThumbnailStudioSettingsStore:
    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)

    def path_for(self, channel: str) -> Path:
        folder = StoragePaths(self._data_root).cache / "thumbnails" / channel_id(channel)
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "studio_settings.json"

    def load(self, channel: str) -> ThumbnailStudioSettings:
        path = self.path_for(channel)
        if not path.is_file():
            return ThumbnailStudioSettings()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ThumbnailStudioSettings()
        return ThumbnailStudioSettings.from_dict(raw if isinstance(raw, dict) else {})

    def save(self, channel: str, settings: ThumbnailStudioSettings) -> Path:
        path = self.path_for(channel)
        path.write_text(json.dumps(settings.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path


def _clamp(value: Any, default: float, lo: float = 0.0, hi: float = 100.0) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, num))
