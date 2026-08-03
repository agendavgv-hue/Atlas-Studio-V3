"""Channel production profile — single source of truth for production defaults.

Projects copy this snapshot at create time. Later channel edits do not change
existing projects. Global AppConfig remains fallback only when a field is empty.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.channels.models import Channel


PROFILE_SCHEMA_VERSION = 1


@dataclass
class ChannelProductionProfile:
    """Complete production configuration owned by one channel."""

    schema_version: int = PROFILE_SCHEMA_VERSION
    channel_name: str = ""
    folder_name: str = ""
    description: str = ""

    # Branding
    logo: str = ""
    banner: str = ""
    brand_colors: dict[str, str] = field(default_factory=dict)
    intro: str = ""
    outro: str = ""

    # Voice
    voice: dict[str, Any] = field(default_factory=dict)
    voice_provider: str = ""

    # AI
    ai_provider: str = ""
    ai_model: str = ""

    # Prompts / image
    prompt_template: str = ""
    image_style: str = ""
    image_prompt: str = ""
    negative_prompt: str = ""
    thumbnail_prompt: str = ""

    # Movie / export
    movie: dict[str, Any] = field(default_factory=dict)
    export: dict[str, Any] = field(default_factory=dict)
    music: dict[str, Any] = field(default_factory=dict)
    subtitles: dict[str, Any] = field(default_factory=dict)
    resolution: str = "1920x1080"
    output_folder: str = ""
    upload_defaults: dict[str, Any] = field(default_factory=dict)

    # SEO placeholder
    seo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ChannelProductionProfile:
        raw = dict(data or {})
        colors = raw.get("brand_colors")
        if not isinstance(colors, dict):
            colors = {}
        return cls(
            schema_version=int(raw.get("schema_version") or PROFILE_SCHEMA_VERSION),
            channel_name=str(raw.get("channel_name") or ""),
            folder_name=str(raw.get("folder_name") or ""),
            description=str(raw.get("description") or ""),
            logo=str(raw.get("logo") or ""),
            banner=str(raw.get("banner") or ""),
            brand_colors={str(k): str(v) for k, v in colors.items()},
            intro=str(raw.get("intro") or ""),
            outro=str(raw.get("outro") or raw.get("outro_line") or "").strip(),
            voice=dict(raw.get("voice") or {}),
            voice_provider=str(raw.get("voice_provider") or ""),
            ai_provider=str(raw.get("ai_provider") or ""),
            ai_model=str(raw.get("ai_model") or ""),
            prompt_template=str(raw.get("prompt_template") or ""),
            image_style=str(raw.get("image_style") or ""),
            image_prompt=str(raw.get("image_prompt") or ""),
            negative_prompt=str(raw.get("negative_prompt") or ""),
            thumbnail_prompt=str(raw.get("thumbnail_prompt") or ""),
            movie=dict(raw.get("movie") or {}),
            export=dict(raw.get("export") or {}),
            music=dict(raw.get("music") or {}),
            subtitles=dict(raw.get("subtitles") or {}),
            resolution=str(raw.get("resolution") or "1920x1080"),
            output_folder=str(raw.get("output_folder") or ""),
            upload_defaults=dict(raw.get("upload_defaults") or {}),
            seo=dict(raw.get("seo") or {}),
        )

    @classmethod
    def from_channel(cls, channel: Channel) -> ChannelProductionProfile:
        """Build the live profile from channel.json (+ studio dict)."""
        studio = dict(channel.studio or {})
        colors = studio.get("brand_colors")
        if not isinstance(colors, dict):
            colors = {}
        voice = dict(channel.voice or {})
        provider = str(
            studio.get("ai_provider")
            or voice.get("provider")
            or studio.get("voice_provider")
            or ""
        )
        return cls(
            channel_name=channel.name,
            folder_name=channel.folder_name,
            description=channel.description,
            logo=str(channel.logo or ""),
            banner=str(channel.banner or ""),
            brand_colors={str(k): str(v) for k, v in colors.items()},
            intro=str(studio.get("intro") or ""),
            outro=(channel.outro_line or str(studio.get("outro") or "")).strip(),
            voice=voice,
            voice_provider=str(
                voice.get("provider") or studio.get("voice_provider") or ""
            ),
            ai_provider=str(studio.get("ai_provider") or provider or "ollama"),
            ai_model=str(studio.get("ai_model") or ""),
            prompt_template=str(studio.get("prompt_template") or ""),
            image_style=str(studio.get("image_style") or ""),
            image_prompt=channel.image_prompt
            or str(studio.get("image_style") or studio.get("prompt_template") or ""),
            negative_prompt=channel.negative_prompt,
            thumbnail_prompt=channel.thumbnail_prompt,
            movie=dict(channel.movie or {}),
            export=dict(studio.get("export") or {}),
            music=dict(studio.get("music") or {}),
            subtitles=dict(studio.get("subtitles") or {}),
            resolution=str(studio.get("resolution") or "1920x1080"),
            output_folder=str(studio.get("output_folder") or ""),
            upload_defaults=dict(studio.get("upload_defaults") or {}),
            seo=dict(channel.seo or {}),
        )

    def apply_to_channel(self, channel: Channel) -> Channel:
        """Write profile fields back onto the channel (master config)."""
        channel.description = self.description
        channel.logo = self.logo or None
        channel.banner = self.banner or None
        channel.outro_line = self.outro
        channel.image_prompt = self.image_prompt
        channel.negative_prompt = self.negative_prompt
        channel.thumbnail_prompt = self.thumbnail_prompt
        channel.voice = dict(self.voice or {})
        if self.voice_provider:
            channel.voice["provider"] = self.voice_provider
        channel.movie = dict(self.movie or {})
        channel.seo = dict(self.seo or {})
        studio = dict(channel.studio or {})
        studio.update(
            {
                "brand_colors": dict(self.brand_colors or {}),
                "intro": self.intro,
                "outro": self.outro,
                "ai_provider": self.ai_provider,
                "ai_model": self.ai_model,
                "prompt_template": self.prompt_template,
                "image_style": self.image_style,
                "resolution": self.resolution,
                "output_folder": self.output_folder,
                "export": dict(self.export or {}),
                "music": dict(self.music or {}),
                "subtitles": dict(self.subtitles or {}),
                "upload_defaults": dict(self.upload_defaults or {}),
                "voice_provider": self.voice_provider,
                "voice_style": ",".join(
                    str(t) for t in (self.voice.get("style_tags") or []) if t
                ),
            }
        )
        channel.studio = studio
        return channel

    def to_channel_defaults_mapping(self) -> dict[str, Any]:
        """Mapping accepted by ChannelDefaults.from_mapping."""
        image_prompt = self.image_prompt
        if self.image_style and self.image_style not in image_prompt:
            image_prompt = (
                f"{image_prompt}, {self.image_style}".strip(", ").strip()
                if image_prompt
                else self.image_style
            )
        if self.prompt_template and self.prompt_template not in image_prompt:
            image_prompt = (
                f"{image_prompt}, {self.prompt_template}".strip(", ").strip()
                if image_prompt
                else self.prompt_template
            )
        return {
            "name": self.channel_name,
            "image_prompt": image_prompt,
            "negative_prompt": self.negative_prompt,
            "thumbnail_prompt": self.thumbnail_prompt,
            "outro_line": self.outro,
            "voice": dict(self.voice or {}),
            "movie": dict(self.movie or {}),
            "seo": dict(self.seo or {}),
            "ai_provider": self.ai_provider,
            "ai_model": self.ai_model,
            "resolution": self.resolution,
            "output_folder": self.output_folder,
        }

    def summary_lines(self) -> list[str]:
        voice_name = str(self.voice.get("voice_name") or self.voice.get("voice_id") or "—")
        return [
            f"Voice: {voice_name}"
            + (f" ({self.voice_provider})" if self.voice_provider else ""),
            f"AI: {self.ai_provider or '—'}"
            + (f" / {self.ai_model}" if self.ai_model else ""),
            f"Image: {self.image_style or self.image_prompt[:60] or '—'}",
            f"Resolution: {self.resolution or '1920x1080'}",
        ]
