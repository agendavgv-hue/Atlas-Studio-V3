"""Load per-channel thumbnail style packs from channel_style.json.

The Thumbnail Engine never hardcodes Hollow Atlas / Mirror Drift rules —
new channels are added by editing the JSON only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.storage_paths import StoragePaths


@dataclass(frozen=True)
class ChannelThumbnailStyle:
    """Visual rules for one channel's YouTube thumbnails."""

    channel_key: str
    display_name: str
    colors: str
    lighting: str
    style: str
    atmosphere: str
    composition: str
    camera: str
    contrast: str
    texture: str
    background_style: str
    headline_position: str
    headline_color: str
    headline_shadow: str
    hero_scale: str
    depth: str
    negative_prompt: str
    thumbnail_rules: str

    def style_block(self) -> str:
        """Prompt-ready style paragraph (no hero subject)."""
        parts = [
            self.style,
            self.colors,
            self.lighting,
            self.atmosphere,
            self.composition,
            self.camera,
            self.contrast,
            self.texture,
            self.background_style,
            self.hero_scale,
            self.depth,
            f"headline area {self.headline_position}".strip(),
            self.thumbnail_rules,
        ]
        return ", ".join(part.strip() for part in parts if part.strip())


_PACKAGED_STYLE_PATH = Path(__file__).resolve().parent / "channel_style.json"


class ChannelStyleLoader:
    """Resolve ``channel_style.json`` with override → packaged fallback."""

    def __init__(
        self,
        *,
        data_root: Path | None = None,
        project_root: Path | None = None,
        packaged_path: Path | None = None,
    ) -> None:
        self._data_root = data_root
        self._project_root = project_root
        self._packaged_path = packaged_path or _PACKAGED_STYLE_PATH

    def style_file_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        if self._project_root is not None:
            candidates.append(Path(self._project_root) / "channel_style.json")
        if self._data_root is not None:
            root = StoragePaths(self._data_root)
            candidates.append(root.assets / "channel_style.json")
            candidates.append(root.root / "channel_style.json")
        candidates.append(self._packaged_path)
        return candidates

    def resolve_style_path(self) -> Path:
        for path in self.style_file_candidates():
            if path.is_file():
                return path
        return self._packaged_path

    def load_all(self) -> dict[str, ChannelThumbnailStyle]:
        """Merge packaged + override files (overrides win; packaged HA/MD always base)."""
        styles: dict[str, ChannelThumbnailStyle] = {}
        for path in reversed(self.style_file_candidates()):
            if not path.is_file():
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict):
                continue
            for key, entry in raw.items():
                if not isinstance(entry, dict):
                    continue
                styles[str(key)] = _style_from_mapping(str(key), entry)
        return styles

    def get_style(self, channel_name: str) -> ChannelThumbnailStyle:
        styles = self.load_all()
        key = (channel_name or "").strip()
        if key in styles:
            return styles[key]
        lowered = key.casefold()
        for name, style in styles.items():
            if name.casefold() == lowered:
                return style
        return _default_style(key or "Default")


def _default_style(key: str) -> ChannelThumbnailStyle:
    return ChannelThumbnailStyle(
        channel_key=key,
        display_name=key,
        colors="high contrast cinematic color grading",
        lighting="dramatic cinematic lighting, left side darker for headline",
        style="cinematic photorealism, ultra detailed, clean composition, one hero subject",
        atmosphere="professional YouTube thumbnail mood",
        composition="hero on the right third, open left negative space for headline",
        camera="medium cinematic framing, shallow depth of field",
        contrast="high contrast",
        texture="realistic materials",
        background_style="simplified uncluttered background",
        headline_position="left",
        headline_color="high-contrast light text",
        headline_shadow="strong dark shadow",
        hero_scale="hero subject fills about 40 percent of the frame",
        depth="strong depth",
        negative_prompt=(
            "collage, cartoon, clutter, text, watermark, logo, multiple subjects, "
            "busy composition, low contrast"
        ),
        thumbnail_rules=(
            "one hero subject filling about 40 percent of the frame, "
            "left side free for headline, clear background, strong focus, "
            "high contrast, deep depth, cinematic lighting, "
            "instantly readable at small YouTube size"
        ),
    )


def _style_from_mapping(key: str, data: dict[str, Any]) -> ChannelThumbnailStyle:
    return ChannelThumbnailStyle(
        channel_key=key,
        display_name=str(data.get("display_name") or key).strip() or key,
        colors=str(data.get("colors") or "").strip(),
        lighting=str(data.get("lighting") or "").strip(),
        style=str(data.get("style") or "").strip(),
        atmosphere=str(data.get("atmosphere") or "").strip(),
        composition=str(data.get("composition") or "").strip(),
        camera=str(data.get("camera") or "").strip(),
        contrast=str(data.get("contrast") or "").strip(),
        texture=str(data.get("texture") or "").strip(),
        background_style=str(data.get("background_style") or "").strip(),
        headline_position=str(data.get("headline_position") or "left").strip() or "left",
        headline_color=str(data.get("headline_color") or "").strip(),
        headline_shadow=str(data.get("headline_shadow") or "").strip(),
        hero_scale=str(data.get("hero_scale") or "").strip(),
        depth=str(data.get("depth") or "").strip(),
        negative_prompt=str(data.get("negative_prompt") or "").strip(),
        thumbnail_rules=str(
            data.get("thumbnail_rules") or data.get("rules") or ""
        ).strip(),
    )
