"""Persist channel configuration packages under Atlas storage."""

from __future__ import annotations

import json
from pathlib import Path

from app.channels.channel_paths import ChannelPaths
from app.channels.models import Channel


class ChannelStore:
    """Load and save ``channel.json`` files. No Project logic."""

    def __init__(self, paths: ChannelPaths) -> None:
        self._paths = paths

    def exists(self, folder_name: str) -> bool:
        return self._paths.config_file(folder_name).is_file()

    def load(self, folder_name: str) -> Channel:
        path = self._paths.config_file(folder_name)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid channel config: {path}")
        return Channel.from_dict(raw, fallback_name=folder_name)

    def save(self, channel: Channel) -> Path:
        config_dir = self._paths.config_dir(channel.folder_name)
        config_dir.mkdir(parents=True, exist_ok=True)
        path = self._paths.config_file(channel.folder_name)
        path.write_text(
            json.dumps(channel.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def ensure_default(self, folder_name: str) -> Channel:
        if self.exists(folder_name):
            channel = self.load(folder_name)
        else:
            channel = Channel.create_default(folder_name)
            self.save(channel)
        return self._ensure_voice_preferences(channel)

    def _ensure_voice_preferences(self, channel: Channel) -> Channel:
        """Apply suggested channel narrator defaults when none are stored yet."""
        from app.channels.voice_preferences import (
            ChannelVoicePreferences,
            resolve_channel_voice_preferences,
        )

        current = ChannelVoicePreferences.from_mapping(channel.voice)
        if not current.is_empty():
            return channel
        resolved = resolve_channel_voice_preferences(channel.name, channel.voice)
        if resolved.is_empty():
            return channel
        channel.voice = resolved.to_dict()
        self.save(channel)
        return channel
