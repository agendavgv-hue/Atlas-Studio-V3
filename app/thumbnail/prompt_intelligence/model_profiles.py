"""Load model_profiles.json — prompt structure preferences per image model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.storage_paths import StoragePaths


@dataclass(frozen=True)
class ModelPromptProfile:
    """How to assemble prompts for one image model family."""

    key: str
    display_name: str
    separator: str = ". "
    use_commas: bool = False
    prefer_short_blocks: bool = True
    cinematography_bias: bool = False
    max_block_words: int = 20
    label_blocks: bool = False
    quality_tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "separator": self.separator,
            "use_commas": self.use_commas,
            "prefer_short_blocks": self.prefer_short_blocks,
            "cinematography_bias": self.cinematography_bias,
            "max_block_words": self.max_block_words,
            "label_blocks": self.label_blocks,
            "quality_tags": list(self.quality_tags),
            "aliases": list(self.aliases),
            "notes": self.notes,
        }


_PACKAGED = Path(__file__).resolve().parent.parent / "model_profiles.json"


class ModelProfileLoader:
    """Resolve ``model_profiles.json`` with override → packaged fallback."""

    def __init__(
        self,
        *,
        data_root: Path | None = None,
        project_root: Path | None = None,
        packaged_path: Path | None = None,
    ) -> None:
        self._data_root = data_root
        self._project_root = project_root
        self._packaged_path = packaged_path or _PACKAGED

    def candidates(self) -> list[Path]:
        paths: list[Path] = []
        if self._project_root is not None:
            paths.append(Path(self._project_root) / "model_profiles.json")
        if self._data_root is not None:
            root = StoragePaths(self._data_root)
            paths.append(root.assets / "model_profiles.json")
            paths.append(root.root / "model_profiles.json")
        paths.append(self._packaged_path)
        return paths

    def resolve_path(self) -> Path:
        for path in self.candidates():
            if path.is_file():
                return path
        return self._packaged_path

    def load_all(self) -> dict[str, ModelPromptProfile]:
        path = self.resolve_path()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid model_profiles.json: {path}")
        profiles: dict[str, ModelPromptProfile] = {}
        for key, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            profiles[str(key)] = _from_mapping(str(key), entry)
        return profiles

    def get_profile(self, model_name: str = "") -> ModelPromptProfile:
        profiles = self.load_all()
        raw = (model_name or "").strip()
        if not raw:
            return profiles.get("default") or _fallback_default()

        if raw in profiles:
            return profiles[raw]

        lowered = raw.casefold()
        for key, profile in profiles.items():
            if key.casefold() == lowered:
                return profile
            if any(alias.casefold() == lowered for alias in profile.aliases):
                return profile
            if lowered in key.casefold() or key.casefold() in lowered:
                return profile
            if any(alias.casefold() in lowered or lowered in alias.casefold() for alias in profile.aliases):
                return profile

        return profiles.get("default") or _fallback_default()


def _fallback_default() -> ModelPromptProfile:
    return ModelPromptProfile(
        key="default",
        display_name="Default",
        separator=". ",
        prefer_short_blocks=True,
        cinematography_bias=True,
        max_block_words=20,
        quality_tags=(
            "photorealistic",
            "sharp focus",
            "high contrast",
            "readable at small size",
        ),
    )


def _from_mapping(key: str, data: dict[str, Any]) -> ModelPromptProfile:
    tags = data.get("quality_tags") or []
    aliases = data.get("aliases") or []
    return ModelPromptProfile(
        key=key,
        display_name=str(data.get("display_name") or key).strip() or key,
        separator=str(data.get("separator") or ". "),
        use_commas=bool(data.get("use_commas", False)),
        prefer_short_blocks=bool(data.get("prefer_short_blocks", True)),
        cinematography_bias=bool(data.get("cinematography_bias", False)),
        max_block_words=max(4, int(data.get("max_block_words") or 20)),
        label_blocks=bool(data.get("label_blocks", False)),
        quality_tags=tuple(str(item).strip() for item in tags if str(item).strip()),
        aliases=tuple(str(item).strip() for item in aliases if str(item).strip()),
        notes=str(data.get("notes") or "").strip(),
    )
