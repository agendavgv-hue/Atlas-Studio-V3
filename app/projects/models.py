"""Project domain model and lifecycle status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PROJECT_SCHEMA_VERSION = 1

STATUS_DRAFT = "Draft"
STATUS_READY = "Ready"
STATUS_IN_PROGRESS = "In Progress"
STATUS_COMPLETED = "Completed"
STATUS_ARCHIVED = "Archived"

PROJECT_STATUSES: tuple[str, ...] = (
    STATUS_DRAFT,
    STATUS_READY,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_ARCHIVED,
)

# Blueprint workflow order — shell only in Phase 3.
WORKFLOW_STEPS: tuple[str, ...] = (
    "Idea",
    "Script",
    "Production Sheet",
    "Images",
    "Voice",
    "Movie",
    "Thumbnail",
    "SEO",
    "Export",
)


@dataclass
class Project:
    """A production project belonging to exactly one channel."""

    name: str
    folder_name: str
    channel_name: str
    idea: str = ""
    status: str = STATUS_DRAFT
    schema_version: int = PROJECT_SCHEMA_VERSION
    script: dict[str, Any] | None = None
    production_sheet: dict[str, Any] | None = None
    images: dict[str, Any] | None = None
    voice: dict[str, Any] | None = None
    movie: dict[str, Any] | None = None
    thumbnail: dict[str, Any] | None = None
    seo: dict[str, Any] | None = None
    export: dict[str, Any] | None = None

    @classmethod
    def create_default(
        cls,
        *,
        name: str,
        channel_name: str,
        idea: str = "",
    ) -> Project:
        return cls(
            name=name,
            folder_name=name,
            channel_name=channel_name,
            idea=idea,
            status=STATUS_DRAFT,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "folder_name": self.folder_name,
            "channel_name": self.channel_name,
            "idea": self.idea,
            "status": self.status,
            "script": self.script,
            "production_sheet": self.production_sheet,
            "images": self.images,
            "voice": self.voice,
            "movie": self.movie,
            "thumbnail": self.thumbnail,
            "seo": self.seo,
            "export": self.export,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        fallback_name: str,
        fallback_channel: str,
    ) -> Project:
        name = str(data.get("name") or fallback_name)
        status = str(data.get("status") or STATUS_DRAFT)
        if status not in PROJECT_STATUSES:
            status = STATUS_DRAFT
        return cls(
            name=name,
            folder_name=str(data.get("folder_name") or name),
            channel_name=str(data.get("channel_name") or fallback_channel),
            idea=str(data.get("idea") or ""),
            status=status,
            schema_version=int(data.get("schema_version") or PROJECT_SCHEMA_VERSION),
            script=data.get("script"),
            production_sheet=data.get("production_sheet"),
            images=data.get("images"),
            voice=data.get("voice"),
            movie=data.get("movie"),
            thumbnail=data.get("thumbnail"),
            seo=data.get("seo"),
            export=data.get("export"),
        )
