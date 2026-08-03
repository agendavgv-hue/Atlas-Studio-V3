"""Read-only execution context passed into every pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.projects.models import Project


@dataclass(frozen=True)
class ChannelDefaults:
    """Read-only channel settings available to pipelines.

    Prefer the project's frozen ``channel_snapshot`` when present so later
    channel edits do not change in-flight productions.
    """

    name: str = ""
    image_prompt: str = ""
    negative_prompt: str = ""
    thumbnail_prompt: str = ""
    outro_line: str = ""
    voice: dict[str, Any] = field(default_factory=dict)
    movie: dict[str, Any] = field(default_factory=dict)
    seo: dict[str, Any] = field(default_factory=dict)
    ai_provider: str = ""
    ai_model: str = ""
    resolution: str = ""
    output_folder: str = ""

    @classmethod
    def from_mapping(cls, data: dict[str, Any], *, name: str = "") -> ChannelDefaults:
        return cls(
            name=str(data.get("name") or name),
            image_prompt=str(data.get("image_prompt") or ""),
            negative_prompt=str(data.get("negative_prompt") or ""),
            thumbnail_prompt=str(data.get("thumbnail_prompt") or ""),
            outro_line=str(data.get("outro_line") or "").strip(),
            voice=dict(data.get("voice") or {}),
            movie=dict(data.get("movie") or {}),
            seo=dict(data.get("seo") or {}),
            ai_provider=str(data.get("ai_provider") or ""),
            ai_model=str(data.get("ai_model") or ""),
            resolution=str(data.get("resolution") or ""),
            output_folder=str(data.get("output_folder") or ""),
        )

    @classmethod
    def from_profile(cls, profile) -> ChannelDefaults:
        return cls.from_mapping(profile.to_channel_defaults_mapping())


@dataclass(frozen=True)
class PipelineContext:
    """Everything a pipeline needs without knowing global storage roots."""

    project: Project
    project_dir: Path
    channel_defaults: ChannelDefaults = field(default_factory=ChannelDefaults)
    creative_brief: Any | None = None
    data_root: Path | None = None

    @property
    def channel_name(self) -> str:
        return self.project.channel_name

    @property
    def project_name(self) -> str:
        return self.project.folder_name

    def folder(self, name: str) -> Path:
        """Return a standard project subfolder (script, images, mp4, …)."""
        path = self.project_dir / name
        path.mkdir(parents=True, exist_ok=True)
        return path
