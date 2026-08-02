"""Creative Director section styles — rules of look/feel, never prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.creative.models._util import from_dict, to_dict


@dataclass
class BrandStyle:
    logo: str = ""
    watermark: str = ""
    colors: list[str] = field(default_factory=list)
    fonts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BrandStyle:
        return from_dict(cls, data)


@dataclass
class VisualStyle:
    realism: str = "photorealistic"
    cinematic: str = "high"
    darkness: str = "medium"
    color_palette: str = ""
    contrast: str = "high"
    lighting: str = "cinematic"
    depth: str = "strong"
    image_quality: str = "ultra"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> VisualStyle:
        return from_dict(cls, data)


@dataclass
class ThumbnailStyleRules:
    layout: str = "subject_right_title_left"
    logo_position: str = "bottom_left"
    text_position: str = "left"
    subject_scale: str = "large"
    negative_space: str = "left"
    max_words: int = 4
    ctr_style: str = "curiosity"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ThumbnailStyleRules:
        raw = dict(data or {})
        if "max_words" in raw:
            try:
                raw["max_words"] = int(raw["max_words"])
            except (TypeError, ValueError):
                raw.pop("max_words", None)
        return from_dict(cls, raw)


@dataclass
class MovieStyleRules:
    camera_style: str = "cinematic"
    zoom_style: str = "slow_in"
    pans: str = "subtle"
    transitions: str = "crossfade"
    particles: str = "none"
    fog: str = "none"
    pacing: str = "documentary"
    shot_length: float = 4.0

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MovieStyleRules:
        raw = dict(data or {})
        if "shot_length" in raw:
            try:
                raw["shot_length"] = float(raw["shot_length"])
            except (TypeError, ValueError):
                raw.pop("shot_length", None)
        return from_dict(cls, raw)


@dataclass
class StoryStyleRules:
    hook_style: str = "curiosity-first"
    suspense: str = "medium"
    cliffhangers: str = "occasional"
    endings: str = "reflective"
    pace: str = "steady"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> StoryStyleRules:
        return from_dict(cls, data)


@dataclass
class VoiceStyleRules:
    provider: str = "kokoro"
    voice: str = ""
    speed: float = 1.0
    emotion: str = "calm"

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> VoiceStyleRules:
        raw = dict(data or {})
        if "speed" in raw:
            try:
                raw["speed"] = float(raw["speed"])
            except (TypeError, ValueError):
                raw.pop("speed", None)
        return from_dict(cls, raw)


@dataclass
class MusicStyleRules:
    genre: str = ""
    ducking: str = "voice_priority"
    volume: float = 0.35
    mood: str = ""

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MusicStyleRules:
        raw = dict(data or {})
        if "volume" in raw:
            try:
                raw["volume"] = float(raw["volume"])
            except (TypeError, ValueError):
                raw.pop("volume", None)
        return from_dict(cls, raw)
