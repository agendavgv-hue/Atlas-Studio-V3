"""Load Channel DNA — full visual identity packs from channel_dna.json.

Style packs describe how to light a frame. DNA describes what makes a
channel instantly recognizable without a logo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.storage_paths import StoragePaths


@dataclass(frozen=True)
class VisualLanguage:
    simplicity: str = "high"
    hero_subjects: int = 1
    composition: str = "clean"
    background: str = "supporting only"
    contrast: str = "high"
    headline_side: str = "left"
    headline_size: str = "very_large"
    empty_space: str = "required"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ColorLanguage:
    primary: str = ""
    secondary: str = ""
    accent: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChannelDNA:
    """Complete design language for one channel."""

    channel_key: str
    display_name: str
    signature: str
    emotion: tuple[str, ...] = ()
    visual_language: VisualLanguage = field(default_factory=VisualLanguage)
    color_language: ColorLanguage = field(default_factory=ColorLanguage)
    identity_rules: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_key": self.channel_key,
            "display_name": self.display_name,
            "signature": self.signature,
            "emotion": list(self.emotion),
            "visual_language": self.visual_language.to_dict(),
            "color_language": self.color_language.to_dict(),
            "identity_rules": list(self.identity_rules),
        }

    def dna_block(self) -> str:
        """Prompt-ready Channel DNA paragraph."""
        vl = self.visual_language
        cl = self.color_language
        emotions = ", ".join(self.emotion) if self.emotion else ""
        rules = "; ".join(self.identity_rules) if self.identity_rules else ""
        parts = [
            f"Channel DNA ({self.display_name})",
            self.signature,
            f"brand emotions: {emotions}" if emotions else "",
            (
                f"visual language: simplicity={vl.simplicity}, "
                f"exactly {vl.hero_subjects} hero subject(s), "
                f"composition={vl.composition}, background={vl.background}, "
                f"contrast={vl.contrast}, headline_side={vl.headline_side}, "
                f"headline_size={vl.headline_size}, empty_space={vl.empty_space}"
            ),
            (
                f"color language: primary={cl.primary}, "
                f"secondary={cl.secondary}, accent={cl.accent}"
            ),
            f"identity rules: {rules}" if rules else "",
        ]
        return ". ".join(part.strip().rstrip(".") for part in parts if part.strip()) + "."


_PACKAGED_DNA_PATH = Path(__file__).resolve().parent / "channel_dna.json"


class ChannelDNALoader:
    """Resolve ``channel_dna.json`` with override → packaged fallback."""

    def __init__(
        self,
        *,
        data_root: Path | None = None,
        project_root: Path | None = None,
        packaged_path: Path | None = None,
    ) -> None:
        self._data_root = data_root
        self._project_root = project_root
        self._packaged_path = packaged_path or _PACKAGED_DNA_PATH

    def dna_file_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        if self._project_root is not None:
            candidates.append(Path(self._project_root) / "channel_dna.json")
        if self._data_root is not None:
            root = StoragePaths(self._data_root)
            candidates.append(root.assets / "channel_dna.json")
            candidates.append(root.root / "channel_dna.json")
        candidates.append(self._packaged_path)
        return candidates

    def resolve_dna_path(self) -> Path:
        for path in self.dna_file_candidates():
            if path.is_file():
                return path
        return self._packaged_path

    def load_all(self) -> dict[str, ChannelDNA]:
        path = self.resolve_dna_path()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid channel_dna.json (expected object): {path}")
        packs: dict[str, ChannelDNA] = {}
        for key, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            packs[str(key)] = _dna_from_mapping(str(key), entry)
        return packs

    def get_dna(self, channel_name: str) -> ChannelDNA:
        packs = self.load_all()
        key = (channel_name or "").strip()
        if key in packs:
            return packs[key]
        lowered = key.casefold()
        for name, dna in packs.items():
            if name.casefold() == lowered:
                return dna
        return _default_dna(key or "Default")


def _default_dna(key: str) -> ChannelDNA:
    return ChannelDNA(
        channel_key=key,
        display_name=key,
        signature=(
            f"A {key} thumbnail is instantly recognizable: one hero, "
            "high contrast, clean composition, required empty headline space."
        ),
        emotion=("curiosity", "discovery"),
        visual_language=VisualLanguage(),
        color_language=ColorLanguage(
            primary="high contrast light",
            secondary="deep dark",
            accent="subtle highlight",
        ),
        identity_rules=(
            "one hero only",
            "background supporting only",
            "left side empty for headline",
            "readable at small YouTube size",
        ),
    )


def _dna_from_mapping(key: str, data: dict[str, Any]) -> ChannelDNA:
    visual_raw = data.get("visual_language") if isinstance(data.get("visual_language"), dict) else {}
    color_raw = data.get("color_language") if isinstance(data.get("color_language"), dict) else {}
    emotions = data.get("emotion") or []
    rules = data.get("identity_rules") or []
    try:
        hero_subjects = int(visual_raw.get("hero_subjects", 1) or 1)
    except (TypeError, ValueError):
        hero_subjects = 1
    return ChannelDNA(
        channel_key=key,
        display_name=str(data.get("display_name") or key).strip() or key,
        signature=str(data.get("signature") or "").strip(),
        emotion=tuple(str(item).strip() for item in emotions if str(item).strip()),
        visual_language=VisualLanguage(
            simplicity=str(visual_raw.get("simplicity") or "high").strip() or "high",
            hero_subjects=max(1, hero_subjects),
            composition=str(visual_raw.get("composition") or "clean").strip() or "clean",
            background=str(visual_raw.get("background") or "supporting only").strip()
            or "supporting only",
            contrast=str(visual_raw.get("contrast") or "high").strip() or "high",
            headline_side=str(visual_raw.get("headline_side") or "left").strip() or "left",
            headline_size=str(visual_raw.get("headline_size") or "very_large").strip()
            or "very_large",
            empty_space=str(visual_raw.get("empty_space") or "required").strip() or "required",
        ),
        color_language=ColorLanguage(
            primary=str(color_raw.get("primary") or "").strip(),
            secondary=str(color_raw.get("secondary") or "").strip(),
            accent=str(color_raw.get("accent") or "").strip(),
        ),
        identity_rules=tuple(str(item).strip() for item in rules if str(item).strip()),
    )
