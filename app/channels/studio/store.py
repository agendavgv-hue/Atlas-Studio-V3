"""Persist Channel Studio JSON + reference folders."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.channels.studio.models import (
    ChannelGoals,
    ChannelPersonality,
    ChannelStudioPack,
    ImageStudioConfig,
    MovieStudioConfig,
    MusicStudioConfig,
    StoryStudioConfig,
    StudioGeneral,
    ThumbnailStudioConfig,
    VoiceStudioConfig,
)
from app.channels.studio.paths import (
    BRAND_KIT_FILE,
    CREATIVE_RULES_FILE,
    GENERAL_FILE,
    GOALS_FILE,
    IMAGE_DNA_FILE,
    IMAGE_SETTINGS_FILE,
    MOVIE_DNA_FILE,
    MUSIC_DNA_FILE,
    PERSONALITY_FILE,
    REFERENCE_KINDS,
    STORY_DNA_FILE,
    THUMBNAIL_DNA_FILE,
    THUMBNAIL_SETTINGS_FILE,
    VOICE_DNA_FILE,
    channel_studio_dir,
    reference_kind_dir,
    references_root,
)
from app.creative.models.brand_kit import BrandKit
from app.creative.models.rules import CreativeRule, default_rules


class ChannelStudioStore:
    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)

    def root(self, folder_name: str) -> Path:
        path = channel_studio_dir(self._data_root, folder_name)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_references(self, folder_name: str) -> Path:
        root = references_root(self._data_root, folder_name)
        root.mkdir(parents=True, exist_ok=True)
        for kind in REFERENCE_KINDS:
            (root / kind).mkdir(parents=True, exist_ok=True)
        return root

    def load_basics(self, folder_name: str) -> ChannelStudioPack:
        """Light open path — general + brand only. No reference scans, no DNA."""
        base = self.root(folder_name)
        return ChannelStudioPack(
            folder_name=folder_name,
            general=StudioGeneral.from_dict(_read_json(base / GENERAL_FILE)),
            brand=BrandKit.from_dict(_read_json(base / BRAND_KIT_FILE)),
        )

    def load_section(self, folder_name: str, section: str) -> Any:
        """Load one Channel Studio section from disk."""
        key = (section or "").strip().casefold()
        base = self.root(folder_name)
        if key == "general":
            return StudioGeneral.from_dict(_read_json(base / GENERAL_FILE))
        if key == "personality":
            return ChannelPersonality.from_dict(_read_json(base / PERSONALITY_FILE))
        if key == "brand":
            return BrandKit.from_dict(_read_json(base / BRAND_KIT_FILE))
        if key == "thumbnail":
            return ThumbnailStudioConfig.from_dict(
                _read_json(base / THUMBNAIL_SETTINGS_FILE)
            )
        if key == "image":
            return ImageStudioConfig.from_dict(_read_json(base / IMAGE_SETTINGS_FILE))
        if key == "movie":
            return MovieStudioConfig.from_dict(_read_json(base / MOVIE_DNA_FILE))
        if key == "story":
            return StoryStudioConfig.from_dict(_read_json(base / STORY_DNA_FILE))
        if key == "voice":
            return VoiceStudioConfig.from_dict(_read_json(base / VOICE_DNA_FILE))
        if key == "music":
            return MusicStudioConfig.from_dict(_read_json(base / MUSIC_DNA_FILE))
        if key == "rules":
            rules_raw = _read_json(base / CREATIVE_RULES_FILE)
            rules_list = (
                rules_raw.get("rules") if isinstance(rules_raw.get("rules"), list) else None
            )
            if rules_list is None:
                return default_rules()
            return [
                CreativeRule.from_dict(item)
                for item in rules_list
                if isinstance(item, dict)
            ]
        if key == "goals":
            return ChannelGoals.from_dict(_read_json(base / GOALS_FILE))
        if key == "advanced":
            self.ensure_references(folder_name)
            return {
                "root": str(base),
                "counts": self.reference_counts(folder_name),
                "thumbnail_dna": _read_json(base / THUMBNAIL_DNA_FILE),
                "image_dna": _read_json(base / IMAGE_DNA_FILE),
            }
        raise ValueError(f"Unknown Channel Studio section: {section}")

    def apply_section(self, pack: ChannelStudioPack, section: str, payload: Any) -> None:
        """Write a loaded section payload into an in-memory pack."""
        key = (section or "").strip().casefold()
        if key == "general":
            pack.general = payload
        elif key == "personality":
            pack.personality = payload
        elif key == "brand":
            pack.brand = payload
        elif key == "thumbnail":
            pack.thumbnail = payload
        elif key == "image":
            pack.image = payload
        elif key == "movie":
            pack.movie = payload
        elif key == "story":
            pack.story = payload
        elif key == "voice":
            pack.voice = payload
        elif key == "music":
            pack.music = payload
        elif key == "rules":
            pack.rules = list(payload or default_rules())
        elif key == "goals":
            pack.goals = payload
        elif key == "advanced":
            if isinstance(payload, dict):
                pack.thumbnail_dna = dict(payload.get("thumbnail_dna") or {})
                pack.image_dna = dict(payload.get("image_dna") or {})
        else:
            raise ValueError(f"Unknown Channel Studio section: {section}")

    def load(self, folder_name: str) -> ChannelStudioPack:
        pack = self.load_basics(folder_name)
        self.ensure_references(folder_name)
        for key in (
            "personality",
            "thumbnail",
            "image",
            "movie",
            "story",
            "voice",
            "music",
            "rules",
            "goals",
            "advanced",
        ):
            self.apply_section(pack, key, self.load_section(folder_name, key))
        return pack

    def save(self, pack: ChannelStudioPack) -> Path:
        base = self.root(pack.folder_name)
        self.ensure_references(pack.folder_name)
        _write_json(base / GENERAL_FILE, pack.general.to_dict())
        _write_json(base / PERSONALITY_FILE, pack.personality.to_dict())
        _write_json(base / BRAND_KIT_FILE, pack.brand.to_dict())
        _write_json(base / THUMBNAIL_SETTINGS_FILE, pack.thumbnail.to_dict())
        _write_json(base / IMAGE_SETTINGS_FILE, pack.image.to_dict())
        _write_json(base / MOVIE_DNA_FILE, pack.movie.to_dict())
        _write_json(base / STORY_DNA_FILE, pack.story.to_dict())
        _write_json(base / VOICE_DNA_FILE, pack.voice.to_dict())
        _write_json(base / MUSIC_DNA_FILE, pack.music.to_dict())
        _write_json(
            base / CREATIVE_RULES_FILE,
            {"rules": [r.to_dict() for r in pack.rules]},
        )
        _write_json(base / GOALS_FILE, pack.goals.to_dict())
        if pack.thumbnail_dna:
            _write_json(base / THUMBNAIL_DNA_FILE, pack.thumbnail_dna)
        if pack.image_dna:
            _write_json(base / IMAGE_DNA_FILE, pack.image_dna)
        return base

    def list_references(self, folder_name: str, kind: str) -> list[Path]:
        folder = reference_kind_dir(self._data_root, folder_name, kind)
        if not folder.is_dir():
            return []
        return sorted(
            [p for p in folder.iterdir() if p.is_file()],
            key=lambda p: p.name.casefold(),
        )

    def add_reference(self, folder_name: str, kind: str, source: Path) -> Path:
        src = Path(source)
        if not src.is_file():
            raise FileNotFoundError(str(src))
        dest_dir = reference_kind_dir(self._data_root, folder_name, kind)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if dest.exists():
            stem, suffix = src.stem, src.suffix
            i = 2
            while dest.exists():
                dest = dest_dir / f"{stem}_{i}{suffix}"
                i += 1
        shutil.copy2(src, dest)
        return dest

    def delete_reference(self, folder_name: str, kind: str, target: Path) -> None:
        tgt = Path(target).resolve()
        allowed = {p.resolve() for p in self.list_references(folder_name, kind)}
        if tgt not in allowed:
            raise FileNotFoundError(str(target))
        tgt.unlink(missing_ok=True)

    def reference_counts(self, folder_name: str) -> dict[str, int]:
        self.ensure_references(folder_name)
        return {k: len(self.list_references(folder_name, k)) for k in REFERENCE_KINDS}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
