"""Channel domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CHANNEL_SCHEMA_VERSION = 2


@dataclass
class Channel:
    """A YouTube channel known to Atlas Studio.

    Phase 2 stores identity and reserved settings placeholders only.
    Feature editors for prompts/voice/movie/SEO arrive in later phases.
    """

    name: str
    folder_name: str
    schema_version: int = CHANNEL_SCHEMA_VERSION
    description: str = ""
    logo: str | None = None
    banner: str | None = None
    image_prompt: str = ""
    negative_prompt: str = ""
    thumbnail_prompt: str = ""
    outro_line: str = ""
    voice: dict[str, Any] = field(default_factory=dict)
    movie: dict[str, Any] = field(default_factory=dict)
    seo: dict[str, Any] = field(default_factory=dict)
    # Channel production defaults — master config for new projects.
    studio: dict[str, Any] = field(default_factory=dict)

    def production_profile(self):
        """Live production profile (channel is the master)."""
        from app.channels.production_profile import ChannelProductionProfile

        return ChannelProductionProfile.from_channel(self)

    @classmethod
    def create_default(cls, name: str) -> Channel:
        return cls(name=name, folder_name=name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "folder_name": self.folder_name,
            "description": self.description,
            "logo": self.logo,
            "banner": self.banner,
            "image_prompt": self.image_prompt,
            "negative_prompt": self.negative_prompt,
            "thumbnail_prompt": self.thumbnail_prompt,
            "outro_line": self.outro_line,
            "voice": self.voice,
            "movie": self.movie,
            "seo": self.seo,
            "studio": self.studio,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], fallback_name: str) -> Channel:
        name = str(data.get("name") or fallback_name)
        folder_name = str(data.get("folder_name") or name)
        return cls(
            name=name,
            folder_name=folder_name,
            schema_version=int(data.get("schema_version") or CHANNEL_SCHEMA_VERSION),
            description=str(data.get("description") or ""),
            logo=data.get("logo"),
            banner=data.get("banner"),
            image_prompt=str(data.get("image_prompt") or ""),
            negative_prompt=str(data.get("negative_prompt") or ""),
            thumbnail_prompt=str(data.get("thumbnail_prompt") or ""),
            outro_line=str(data.get("outro_line") or "").strip(),
            voice=dict(data.get("voice") or {}),
            movie=dict(data.get("movie") or {}),
            seo=dict(data.get("seo") or {}),
            studio=dict(data.get("studio") or {}),
        )
