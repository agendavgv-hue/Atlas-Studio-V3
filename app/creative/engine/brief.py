"""Creative Brief — single object every generator consumes."""

from __future__ import annotations

from dataclasses import dataclass, field
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
from app.creative.models.brand_kit import BrandKit
from app.creative.models.rules import CreativeRule


@dataclass
class ReferenceSummary:
    kind: str
    count: int
    names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "count": self.count, "names": list(self.names)}


@dataclass
class ProjectBrief:
    topic: str = ""
    idea: str = ""
    folder_name: str = ""
    script_excerpt: str = ""
    sheet_excerpt: str = ""
    primary_subject: str = ""
    primary_location: str = ""
    primary_emotion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "idea": self.idea,
            "folder_name": self.folder_name,
            "script_excerpt": self.script_excerpt[:500],
            "sheet_excerpt": self.sheet_excerpt[:500],
            "primary_subject": self.primary_subject,
            "primary_location": self.primary_location,
            "primary_emotion": self.primary_emotion,
        }


@dataclass
class CreativeBrief:
    """Master creative identity for one channel + optional project."""

    channel_name: str
    folder_name: str
    general: StudioGeneral
    brand: BrandKit
    thumbnail: ThumbnailStudioConfig
    image: ImageStudioConfig
    movie: MovieStudioConfig
    story: StoryStudioConfig
    voice: VoiceStudioConfig
    music: MusicStudioConfig
    personality: ChannelPersonality
    rules: list[CreativeRule]
    goals: ChannelGoals
    references: list[ReferenceSummary] = field(default_factory=list)
    project: ProjectBrief = field(default_factory=ProjectBrief)
    thumbnail_dna: dict[str, Any] = field(default_factory=dict)
    image_dna: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_pack(
        cls,
        pack: ChannelStudioPack,
        *,
        references: list[ReferenceSummary] | None = None,
        project: ProjectBrief | None = None,
    ) -> CreativeBrief:
        return cls(
            channel_name=pack.general.name or pack.folder_name,
            folder_name=pack.folder_name,
            general=pack.general,
            brand=pack.brand,
            thumbnail=pack.thumbnail,
            image=pack.image,
            movie=pack.movie,
            story=pack.story,
            voice=pack.voice,
            music=pack.music,
            personality=pack.personality,
            rules=list(pack.rules),
            goals=pack.goals,
            references=list(references or []),
            project=project or ProjectBrief(),
            thumbnail_dna=dict(pack.thumbnail_dna or {}),
            image_dna=dict(pack.image_dna or {}),
        )

    @property
    def enabled_rules(self) -> list[CreativeRule]:
        return [r for r in self.rules if r.enabled]

    @property
    def reference_count(self) -> int:
        return sum(item.count for item in self.references)

    def reference_names(self, kind: str) -> list[str]:
        for item in self.references:
            if item.kind == kind:
                return list(item.names)
        return []
