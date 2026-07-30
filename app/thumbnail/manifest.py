"""Thumbnail Manifest — durable plan for one thumbnail run.

Written as ``thumbnail/thumbnail_manifest.json`` beside ``thumbnail.png``.
Reserved fields support future Thumbnail Engine upgrades without redesign.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.naming import THUMBNAIL_BASENAME, THUMBNAIL_FOLDER


MANIFEST_VERSION = 1


@dataclass
class ManifestBranding:
    """Optional branding — unused unless assets are present."""

    logo_path: str | None = None
    watermark_path: str | None = None
    brand_colors: list[str] = field(default_factory=list)
    preset_id: str | None = None
    # Future: templates, channel style packs


@dataclass
class ManifestText:
    """Reserved text / title overlay placeholders."""

    title: str = ""
    hook: str = ""
    placeholders: dict[str, str] = field(default_factory=dict)


@dataclass
class ManifestOutput:
    """Where the thumbnail lands. Sprint 9 exports PNG only."""

    folder: str = THUMBNAIL_FOLDER
    filename: str = THUMBNAIL_BASENAME
    width: int = 1280
    height: int = 720


@dataclass
class ManifestGeneration:
    """Snapshot of provider-ready settings used for generate modes.

    Provider-specific details stay out of the pipeline; this records what
    was requested through the Provider Framework.
    """

    provider_id: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    width: int = 0
    height: int = 0
    seed: int = -1
    model: str = ""
    steps: int = 0
    cfg_scale: float = 0.0
    sampler: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThumbnailManifest:
    """Complete durable plan for one thumbnail export."""

    version: int = MANIFEST_VERSION
    mode: str = ThumbnailMode.SELECT.value
    source_image_path: str | None = None
    rationale: str = ""
    branding: ManifestBranding = field(default_factory=ManifestBranding)
    text: ManifestText = field(default_factory=ManifestText)
    output: ManifestOutput = field(default_factory=ManifestOutput)
    generation: ManifestGeneration | None = None
    exported: bool = False
    # Future: AI score, multi-candidate metadata (no candidates folder in Sprint 9).
    ai_score: float | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThumbnailManifest:
        raw = dict(data or {})
        branding_raw = raw.get("branding") if isinstance(raw.get("branding"), dict) else {}
        text_raw = raw.get("text") if isinstance(raw.get("text"), dict) else {}
        output_raw = raw.get("output") if isinstance(raw.get("output"), dict) else {}
        generation_raw = (
            raw.get("generation") if isinstance(raw.get("generation"), dict) else None
        )

        generation = None
        if generation_raw is not None:
            generation = ManifestGeneration(
                provider_id=str(generation_raw.get("provider_id") or ""),
                prompt=str(generation_raw.get("prompt") or ""),
                negative_prompt=str(generation_raw.get("negative_prompt") or ""),
                width=int(generation_raw.get("width") or 0),
                height=int(generation_raw.get("height") or 0),
                seed=int(generation_raw.get("seed") if generation_raw.get("seed") is not None else -1),
                model=str(generation_raw.get("model") or ""),
                steps=int(generation_raw.get("steps") or 0),
                cfg_scale=float(generation_raw.get("cfg_scale") or 0.0),
                sampler=str(generation_raw.get("sampler") or ""),
                extras=dict(generation_raw.get("extras") or {}),
            )

        ai_score_raw = raw.get("ai_score")
        ai_score: float | None
        try:
            ai_score = float(ai_score_raw) if ai_score_raw is not None else None
        except (TypeError, ValueError):
            ai_score = None

        return cls(
            version=int(raw.get("version") or MANIFEST_VERSION),
            mode=str(raw.get("mode") or ThumbnailMode.SELECT.value),
            source_image_path=raw.get("source_image_path"),
            rationale=str(raw.get("rationale") or ""),
            branding=ManifestBranding(
                logo_path=branding_raw.get("logo_path"),
                watermark_path=branding_raw.get("watermark_path"),
                brand_colors=list(branding_raw.get("brand_colors") or []),
                preset_id=branding_raw.get("preset_id"),
            ),
            text=ManifestText(
                title=str(text_raw.get("title") or ""),
                hook=str(text_raw.get("hook") or ""),
                placeholders=dict(text_raw.get("placeholders") or {}),
            ),
            output=ManifestOutput(
                folder=str(output_raw.get("folder") or THUMBNAIL_FOLDER),
                filename=str(output_raw.get("filename") or THUMBNAIL_BASENAME),
                width=int(output_raw.get("width") or 1280),
                height=int(output_raw.get("height") or 720),
            ),
            generation=generation,
            exported=bool(raw.get("exported", False)),
            ai_score=ai_score,
            extras=dict(raw.get("extras") or {}),
        )

    @classmethod
    def read_json(cls, path: Path) -> ThumbnailManifest:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
