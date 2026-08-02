"""CreativeDirector — channel identity guardian (no generation, no prompts)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.creative.models.rules import CreativeRule, default_rules
from app.creative.models.sections import (
    BrandStyle,
    MovieStyleRules,
    MusicStyleRules,
    StoryStyleRules,
    ThumbnailStyleRules,
    VisualStyle,
    VoiceStyleRules,
)


@dataclass
class CreativeDirector:
    """Creative rules of identity for one channel.

    Does not generate images, scripts, or video — only guards identity.
    """

    channel_name: str = ""
    channel_key: str = ""
    version: int = 1
    brand: BrandStyle = field(default_factory=BrandStyle)
    visual: VisualStyle = field(default_factory=VisualStyle)
    thumbnail: ThumbnailStyleRules = field(default_factory=ThumbnailStyleRules)
    movie: MovieStyleRules = field(default_factory=MovieStyleRules)
    story: StoryStyleRules = field(default_factory=StoryStyleRules)
    voice: VoiceStyleRules = field(default_factory=VoiceStyleRules)
    music: MusicStyleRules = field(default_factory=MusicStyleRules)
    rules: list[CreativeRule] = field(default_factory=default_rules)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "channel_key": self.channel_key,
            "version": self.version,
            "brand": self.brand.to_dict(),
            "visual": self.visual.to_dict(),
            "thumbnail": self.thumbnail.to_dict(),
            "movie": self.movie.to_dict(),
            "story": self.story.to_dict(),
            "voice": self.voice.to_dict(),
            "music": self.music.to_dict(),
            "rules": [rule.to_dict() for rule in self.rules],
            "extras": dict(self.extras),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CreativeDirector:
        raw = dict(data or {})
        rules_raw = raw.get("rules") if isinstance(raw.get("rules"), list) else None
        rules = (
            [CreativeRule.from_dict(item) for item in rules_raw if isinstance(item, dict)]
            if rules_raw is not None
            else default_rules()
        )
        return cls(
            channel_name=str(raw.get("channel_name") or ""),
            channel_key=str(raw.get("channel_key") or ""),
            version=int(raw.get("version") or 1),
            brand=BrandStyle.from_dict(raw.get("brand") if isinstance(raw.get("brand"), dict) else {}),
            visual=VisualStyle.from_dict(
                raw.get("visual") if isinstance(raw.get("visual"), dict) else {}
            ),
            thumbnail=ThumbnailStyleRules.from_dict(
                raw.get("thumbnail") if isinstance(raw.get("thumbnail"), dict) else {}
            ),
            movie=MovieStyleRules.from_dict(
                raw.get("movie") if isinstance(raw.get("movie"), dict) else {}
            ),
            story=StoryStyleRules.from_dict(
                raw.get("story") if isinstance(raw.get("story"), dict) else {}
            ),
            voice=VoiceStyleRules.from_dict(
                raw.get("voice") if isinstance(raw.get("voice"), dict) else {}
            ),
            music=MusicStyleRules.from_dict(
                raw.get("music") if isinstance(raw.get("music"), dict) else {}
            ),
            rules=rules,
            extras=dict(raw.get("extras") or {})
            if isinstance(raw.get("extras"), dict)
            else {},
        )

    def enabled_rules(self) -> list[CreativeRule]:
        return sorted(
            [r for r in self.rules if r.enabled],
            key=lambda r: (-int(r.priority), r.id),
        )

    def rule_summaries(self) -> list[str]:
        return [f"{r.title}: {r.description}".strip(": ") for r in self.enabled_rules()]
