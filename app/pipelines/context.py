"""Read-only execution context passed into every pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.projects.models import Project


@dataclass(frozen=True)
class ChannelDefaults:
    """Read-only channel settings available to pipelines.

    Pipelines may read these values. They must never write channel configuration.
    """

    name: str = ""
    image_prompt: str = ""
    negative_prompt: str = ""
    thumbnail_prompt: str = ""
    voice: dict[str, Any] = field(default_factory=dict)
    movie: dict[str, Any] = field(default_factory=dict)
    seo: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any], *, name: str = "") -> ChannelDefaults:
        return cls(
            name=str(data.get("name") or name),
            image_prompt=str(data.get("image_prompt") or ""),
            negative_prompt=str(data.get("negative_prompt") or ""),
            thumbnail_prompt=str(data.get("thumbnail_prompt") or ""),
            voice=dict(data.get("voice") or {}),
            movie=dict(data.get("movie") or {}),
            seo=dict(data.get("seo") or {}),
        )


@dataclass(frozen=True)
class PipelineContext:
    """Everything a pipeline needs without knowing global storage roots."""

    project: Project
    project_dir: Path
    channel_defaults: ChannelDefaults = field(default_factory=ChannelDefaults)

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
