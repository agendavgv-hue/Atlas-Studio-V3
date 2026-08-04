"""Per-channel narrator preferences (stored in channel.json ``voice``)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.voice_settings import VoiceSettings
from app.providers.voice_base import VoiceInfo
from app.providers.voice_metadata import select_closest_voice


@dataclass
class ChannelVoicePreferences:
    """Preferred narrator for one YouTube channel.

    Defaults are suggestions only — the user may override any field.
    """

    provider: str = ""
    voice_id: str = ""
    voice_name: str = ""
    speed: float = 1.0
    language: str = "en-US"
    gender: str = ""
    style_tags: list[str] = field(default_factory=list)
    # Optional Chatterbox zero-shot clone clip (channel-relative or absolute).
    reference_voice: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> ChannelVoicePreferences:
        raw = data or {}
        styles = raw.get("style_tags") or raw.get("styles") or []
        if isinstance(styles, str):
            style_tags = [part.strip() for part in styles.split(",") if part.strip()]
        elif isinstance(styles, (list, tuple)):
            style_tags = [str(part).strip() for part in styles if str(part).strip()]
        else:
            style_tags = []
        speed = 1.0
        try:
            speed = float(raw.get("speed", 1.0))
        except (TypeError, ValueError):
            speed = 1.0
        speed = max(0.5, min(2.0, speed))
        return cls(
            provider=str(raw.get("provider") or raw.get("voice_provider") or "").strip(),
            voice_id=str(raw.get("voice_id") or "").strip(),
            voice_name=str(raw.get("voice_name") or "").strip(),
            speed=speed,
            language=str(raw.get("language") or "en-US").strip() or "en-US",
            gender=str(raw.get("gender") or "").strip(),
            style_tags=style_tags,
            reference_voice=str(
                raw.get("reference_voice") or raw.get("reference_audio_path") or ""
            ).strip(),
        )

    def is_empty(self) -> bool:
        return not (
            self.provider
            or self.voice_id
            or self.gender
            or self.style_tags
            or self.reference_voice
        )

    def apply_to_settings(self, base: VoiceSettings) -> VoiceSettings:
        """Merge channel prefs over app-level VoiceSettings."""
        return VoiceSettings(
            api_key=base.api_key,
            voice_id=self.voice_id or base.voice_id,
            voice_name=self.voice_name or base.voice_name,
            language=self.language or base.language,
            model=base.model,
            stability=base.stability,
            style=base.style,
            speed=self.speed if self.speed > 0 else base.speed,
            similarity=base.similarity,
            output_format=base.output_format,
            reference_audio_path=self.reference_voice
            or base.reference_audio_path,
        )

    def bind_voice(self, voice: VoiceInfo) -> None:
        self.voice_id = voice.voice_id
        self.voice_name = voice.name
        if voice.language:
            self.language = voice.language
        if voice.gender and not self.gender:
            self.gender = voice.gender


# Suggested channel profiles — defaults only; users may override.
# Kept empty so Atlas never hardcodes channel-name behaviour.
CHANNEL_VOICE_PROFILES: dict[str, ChannelVoicePreferences] = {}


def profile_for_channel(channel_name: str) -> ChannelVoicePreferences | None:
    key = (channel_name or "").strip()
    if key in CHANNEL_VOICE_PROFILES:
        return ChannelVoicePreferences.from_mapping(CHANNEL_VOICE_PROFILES[key].to_dict())
    # Case-insensitive match
    lowered = key.casefold()
    for name, profile in CHANNEL_VOICE_PROFILES.items():
        if name.casefold() == lowered:
            return ChannelVoicePreferences.from_mapping(profile.to_dict())
    return None


def resolve_channel_voice_preferences(
    channel_name: str,
    stored: dict[str, Any] | None,
    *,
    voices: list[VoiceInfo] | None = None,
) -> ChannelVoicePreferences:
    """Load stored prefs, fill profile defaults, optionally auto-pick a voice."""
    prefs = ChannelVoicePreferences.from_mapping(stored)
    profile = profile_for_channel(channel_name)
    if prefs.is_empty() and profile is not None:
        prefs = ChannelVoicePreferences.from_mapping(profile.to_dict())
    elif profile is not None:
        if not prefs.gender:
            prefs.gender = profile.gender
        if not prefs.style_tags:
            prefs.style_tags = list(profile.style_tags)
        if not prefs.provider:
            prefs.provider = profile.provider
        if not prefs.language:
            prefs.language = profile.language

    if not prefs.voice_id and voices:
        match = select_closest_voice(
            voices,
            gender=prefs.gender,
            style_tags=prefs.style_tags,
            language=prefs.language,
        )
        if match is not None:
            prefs.bind_voice(match)
    return prefs
