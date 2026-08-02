"""Channel Studio domain models (config only — no AI)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.channels.studio._util import from_dict, to_dict
from app.creative.models.brand_kit import BrandKit
from app.creative.models.rules import CreativeRule, default_rules

PERSONALITY_TRAITS: tuple[str, ...] = (
    "mystery",
    "wonder",
    "history",
    "science",
    "adventure",
    "luxury",
    "darkness",
    "fantasy",
    "humor",
    "fear",
    "hope",
    "epic",
)

PRIORITY_LABELS: dict[str, int] = {
    "critical": 100,
    "high": 75,
    "medium": 50,
    "low": 25,
}


def priority_label(value: int) -> str:
    if value >= 90:
        return "critical"
    if value >= 65:
        return "high"
    if value >= 40:
        return "medium"
    return "low"


@dataclass
class StudioGeneral:
    name: str = ""
    description: str = ""
    niche: str = ""
    audience: str = ""
    language: str = "en-US"
    tone_of_voice: str = ""
    upload_frequency: str = ""
    channel_type: str = "documentary"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> StudioGeneral:
        return from_dict(cls, data)


@dataclass
class ChannelPersonality:
    """Channel Personality DNA used later by all generators."""

    traits: dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"traits": dict(self.traits), "notes": self.notes}

    @classmethod
    def default_profile(cls) -> ChannelPersonality:
        return cls(
            traits={
                "mystery": 100,
                "wonder": 95,
                "history": 100,
                "science": 85,
                "adventure": 70,
                "luxury": 80,
                "darkness": 90,
                "fantasy": 10,
                "humor": 0,
                "fear": 30,
                "hope": 40,
                "epic": 90,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ChannelPersonality:
        raw = dict(data or {})
        traits_raw = raw.get("traits") if isinstance(raw.get("traits"), dict) else {}
        if not traits_raw:
            profile = cls.default_profile()
            profile.notes = str(raw.get("notes") or "")
            return profile
        traits: dict[str, float] = {}
        for key in PERSONALITY_TRAITS:
            try:
                traits[key] = float(traits_raw.get(key, 50.0))
            except (TypeError, ValueError):
                traits[key] = 50.0
        for key, value in traits_raw.items():
            if key in traits:
                continue
            try:
                traits[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return cls(traits=traits, notes=str(raw.get("notes") or ""))

    def score(self, trait: str) -> float:
        return float(self.traits.get(trait, 50.0))


@dataclass
class ThumbnailStudioConfig:
    max_words: int = 4
    logo_visible: bool = True
    logo_position: str = "auto"
    logo_size: float = 0.12
    contrast: str = "very_high"
    negative_space: str = "auto"
    creativity: float = 60.0
    style_strength: float = 80.0
    brand_strength: float = 85.0
    dominant_subject: str = "one"
    emotion: str = "curiosity"
    cinematic_level: float = 80.0
    realism: float = 85.0
    documentary: float = 70.0
    composition_style: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ThumbnailStudioConfig:
        return from_dict(cls, data)


@dataclass
class ImageStudioConfig:
    model: str = ""
    lora: str = ""
    resolution: str = "1536x864"
    realism: float = 90.0
    detail: str = "ultra"
    lighting: str = "warm_cinematic"
    camera_style: str = "documentary"
    color_palette: str = ""
    image_quality: str = "ultra"
    mood: str = "mystery"
    atmosphere: str = "none"
    film_grain: str = "low"
    texture: str = "stone"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ImageStudioConfig:
        return from_dict(cls, data)


@dataclass
class MovieStudioConfig:
    camera_style: str = "cinematic"
    motion_amount: str = "slow"
    animation_style: str = "slow_in"
    transitions: str = "crossfade"
    zoom_style: str = "slow_in"
    pan_style: str = "subtle"
    particles: str = "none"
    fog: str = "none"
    lighting: str = "warm"
    movie_quality: str = "high"
    preset: str = "documentary_cinematic"
    camera_motion: str = "slow"
    lighting_preset: str = "documentary"
    shot_style: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MovieStudioConfig:
        return from_dict(cls, data)


@dataclass
class StoryStudioConfig:
    hook_style: str = "curiosity-first"
    storytelling_style: str = "documentary"
    pacing: str = "steady"
    cliffhangers: str = "occasional"
    ending_style: str = "reflective"
    humor: str = "none"
    emotion: str = "curiosity"
    documentary_level: float = 80.0
    mystery: float = 80.0
    wonder: float = 70.0
    science: float = 60.0
    history: float = 70.0
    adventure: float = 50.0
    fantasy: float = 10.0
    suspense: float = 60.0
    speculation: float = 55.0
    historical_accuracy: float = 75.0
    open_questions: float = 70.0
    tension: float = 55.0
    hook_type: str = "question"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> StoryStudioConfig:
        return from_dict(cls, data)


@dataclass
class VoiceStudioConfig:
    provider: str = "kokoro"
    voice: str = ""
    voice_id: str = ""
    speed: float = 1.0
    emotion: str = "calm"
    pause_length: str = "natural"
    pronunciation: dict[str, str] = field(default_factory=dict)
    pitch: float = 1.0
    voice_style: str = "documentary"
    accent: str = "neutral"
    age: str = "adult"
    authority: float = 70.0
    warmth: float = 60.0
    curiosity: float = 65.0
    mystery: float = 55.0
    energy: float = 45.0

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> VoiceStudioConfig:
        return from_dict(cls, data)


@dataclass
class MusicStudioConfig:
    genre: str = ""
    mood: str = "mystery"
    volume: float = 0.35
    fade_in: str = "soft"
    fade_out: str = "soft"
    ducking: str = "voice_priority"
    background_level: float = 0.25
    personality: str = "mystery"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MusicStudioConfig:
        return from_dict(cls, data)


@dataclass
class ChannelGoals:
    uploads_per_week: float = 1.0
    subscriber_goal: int = 0
    view_goal: int = 0
    ctr_goal: float = 5.0
    retention_goal: float = 40.0
    rpm_goal: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ChannelGoals:
        return from_dict(cls, data)


@dataclass
class ChannelStudioPack:
    """Complete Channel Studio configuration for one channel folder."""

    folder_name: str
    general: StudioGeneral = field(default_factory=StudioGeneral)
    personality: ChannelPersonality = field(default_factory=ChannelPersonality.default_profile)
    brand: BrandKit = field(default_factory=BrandKit)
    thumbnail: ThumbnailStudioConfig = field(default_factory=ThumbnailStudioConfig)
    image: ImageStudioConfig = field(default_factory=ImageStudioConfig)
    movie: MovieStudioConfig = field(default_factory=MovieStudioConfig)
    story: StoryStudioConfig = field(default_factory=StoryStudioConfig)
    voice: VoiceStudioConfig = field(default_factory=VoiceStudioConfig)
    music: MusicStudioConfig = field(default_factory=MusicStudioConfig)
    rules: list[CreativeRule] = field(default_factory=default_rules)
    goals: ChannelGoals = field(default_factory=ChannelGoals)
    thumbnail_dna: dict[str, Any] = field(default_factory=dict)
    image_dna: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)
