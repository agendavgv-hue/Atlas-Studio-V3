"""CreativeDirectorService — load/save/create identity guardian for a channel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.channels.channel_ids import channel_id
from app.channels.models import Channel
from app.creative.models.brand_kit import BrandKit
from app.creative.models.director import CreativeDirector
from app.creative.models.rules import CreativeRule
from app.creative.models.sections import (
    MovieStyleRules,
    StoryStyleRules,
    ThumbnailStyleRules,
    VisualStyle,
)
from app.creative.models.style_library import StyleLibrary
from app.creative.paths import (
    BRAND_KIT_FILE,
    DIRECTOR_FILE,
    STYLE_LIBRARY_FILE,
    channel_creative_dir,
)
from app.creative.seeding import seed_brand_kit, seed_director, seed_style_library
from app.creative.services.reference_library import ReferenceLibrary
from app.creative.store import load_model, save_model
from app.core.storage_paths import StoragePaths


class CreativeDirectorService:
    """Owns Creative Director, Brand Kit, Style Library, and Reference Library."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        StoragePaths(self._data_root).creative.mkdir(parents=True, exist_ok=True)

    @property
    def data_root(self) -> Path:
        return self._data_root

    def channel_dir(self, channel: str) -> Path:
        return channel_creative_dir(self._data_root, channel)

    def exists(self, channel: str) -> bool:
        return (self.channel_dir(channel) / DIRECTOR_FILE).is_file()

    def create(
        self,
        channel: str,
        *,
        source: Channel | None = None,
        brain: Any | None = None,
        force: bool = False,
    ) -> CreativeDirector:
        name = (channel or "").strip()
        if not name:
            raise ValueError("Channel name is required.")
        if self.exists(name) and not force:
            return self.load(name)

        director = CreativeDirector(
            channel_name=name,
            channel_key=channel_id(name),
        )
        seed_director(director, channel=source, brain=brain)
        self.save(director)

        brand = seed_brand_kit(source, brain)
        style = seed_style_library(source, brain)
        self.save_brand(name, brand)
        self.save_style(name, style)
        self.references(name).ensure_structure()
        return director

    def load(self, channel: str) -> CreativeDirector:
        path = self.channel_dir(channel) / DIRECTOR_FILE
        director = load_model(path, CreativeDirector.from_dict)
        if not director.channel_name:
            director.channel_name = channel.strip()
        if not director.channel_key:
            director.channel_key = channel_id(channel)
        return director

    def save(self, director: CreativeDirector) -> Path:
        if not director.channel_key and director.channel_name:
            director.channel_key = channel_id(director.channel_name)
        path = self.channel_dir(director.channel_name) / DIRECTOR_FILE
        return save_model(path, director)

    def update(self, channel: str, **sections: Any) -> CreativeDirector:
        director = self.load(channel) if self.exists(channel) else self.create(channel)
        allowed = {
            "brand",
            "visual",
            "thumbnail",
            "movie",
            "story",
            "voice",
            "music",
            "rules",
            "extras",
        }
        for key, value in sections.items():
            if key not in allowed:
                raise ValueError(f"Unknown Creative Director section: {key}")
            setattr(director, key, value)
        self.save(director)
        return director

    def ensure(
        self,
        channel: str,
        *,
        source: Channel | None = None,
        brain: Any | None = None,
    ) -> CreativeDirector:
        if self.exists(channel):
            return self.load(channel)
        return self.create(channel, source=source, brain=brain)

    def validate(self, channel: str) -> list[str]:
        """Return human-readable validation issues (empty = ok)."""
        issues: list[str] = []
        if not self.exists(channel):
            return ["Creative Director is missing for this channel."]
        director = self.load(channel)
        if not director.enabled_rules():
            issues.append("No enabled creative rules.")
        if director.thumbnail.max_words < 1:
            issues.append("Thumbnail max_words must be >= 1.")
        if not (0.5 <= director.voice.speed <= 2.0):
            issues.append("Voice speed should be between 0.5 and 2.0.")
        brand = self.get_brand(channel)
        if not brand.primary_color and not director.brand.colors:
            issues.append("Brand colors are not set.")
        style = self.get_style(channel)
        if style.realism < 0 or style.realism > 100:
            issues.append("Style Library realism weight out of range.")
        refs = self.references(channel)
        if not refs.root.is_dir():
            issues.append("Reference Library folders are missing.")
        return issues

    def generate_recommendations(self, channel: str) -> list[str]:
        """Lightweight identity recommendations for editors / future AI Critic."""
        director = self.ensure(channel)
        style = self.get_style(channel)
        brand = self.get_brand(channel)
        tips: list[str] = []
        for rule in director.enabled_rules()[:8]:
            tips.append(f"Keep rule: {rule.title}")
        tips.append(
            f"Thumbnail: {director.thumbnail.text_position} text, "
            f"max {director.thumbnail.max_words} words, "
            f"{director.thumbnail.ctr_style} CTR style"
        )
        tips.append(
            f"Visual: {director.visual.lighting} lighting, "
            f"{director.visual.contrast} contrast, {director.visual.realism}"
        )
        tips.append(
            f"Style weights — realism {style.realism:g}, mystery {style.mystery:g}, "
            f"documentary {style.documentary:g}, darkness {style.darkness:g}"
        )
        if brand.primary_color:
            tips.append(
                f"Brand colors: {brand.primary_color} / "
                f"{brand.secondary_color or '—'} / {brand.accent_color or '—'}"
            )
        counts = self.references(channel).counts()
        empty = [k for k, n in counts.items() if n == 0]
        if empty:
            tips.append(
                "Add references for: " + ", ".join(empty[:6])
                + ("…" if len(empty) > 6 else "")
            )
        return tips

    # --- getters -------------------------------------------------------

    def get_rules(self, channel: str) -> list[CreativeRule]:
        return self.ensure(channel).enabled_rules()

    def get_brand(self, channel: str) -> BrandKit:
        path = self.channel_dir(channel) / BRAND_KIT_FILE
        if not path.is_file():
            kit = BrandKit()
            self.save_brand(channel, kit)
            return kit
        return load_model(path, BrandKit.from_dict)

    def save_brand(self, channel: str, brand: BrandKit) -> Path:
        return save_model(self.channel_dir(channel) / BRAND_KIT_FILE, brand)

    def get_style(self, channel: str) -> StyleLibrary:
        path = self.channel_dir(channel) / STYLE_LIBRARY_FILE
        if not path.is_file():
            style = StyleLibrary()
            self.save_style(channel, style)
            return style
        return load_model(path, StyleLibrary.from_dict)

    def save_style(self, channel: str, style: StyleLibrary) -> Path:
        return save_model(self.channel_dir(channel) / STYLE_LIBRARY_FILE, style)

    def get_thumbnail_style(self, channel: str) -> ThumbnailStyleRules:
        return self.ensure(channel).thumbnail

    def get_movie_style(self, channel: str) -> MovieStyleRules:
        return self.ensure(channel).movie

    def get_story_style(self, channel: str) -> StoryStyleRules:
        return self.ensure(channel).story

    def get_visual_style(self, channel: str) -> VisualStyle:
        return self.ensure(channel).visual

    def references(self, channel: str) -> ReferenceLibrary:
        return ReferenceLibrary(self._data_root, channel)
