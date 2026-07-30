"""Channel application service — create, list, and load channels."""

from __future__ import annotations

import re
from pathlib import Path

from app.channels.channel_discovery import discover_channel_folder_names
from app.channels.channel_paths import ChannelPaths
from app.channels.channel_store import ChannelStore
from app.channels.models import Channel
from app.core.app_config import AppConfig
from app.core.project_root import (
    ProjectRootError,
    ensure_project_root,
    require_project_root,
)
from app.core.storage import Storage

# Forbidden characters for folder/channel names (platform-safe subset).
_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ChannelService:
    """Public channel API. Channels never know about Projects."""

    def __init__(self, storage: Storage, config: AppConfig) -> None:
        self._storage = storage
        self._config = config
        self._active_folder_name: str | None = None

    @property
    def project_root(self) -> Path | None:
        return self._config.project_root

    @property
    def active_channel_name(self) -> str | None:
        return self._active_folder_name

    def set_project_root(self, path: Path) -> Path:
        """Persist Project Root and ensure the directory exists."""
        resolved = ensure_project_root(path)
        self._config.project_root = resolved
        self._config.save()
        return resolved

    def _paths(self) -> ChannelPaths:
        root = require_project_root(self._config.project_root)
        return ChannelPaths(self._storage, root)

    def list_channels(self) -> list[Channel]:
        """Discover library folders and ensure each has Atlas config."""
        try:
            paths = self._paths()
        except ProjectRootError:
            return []

        store = ChannelStore(paths)
        channels: list[Channel] = []
        for name in discover_channel_folder_names(paths.project_root):
            channels.append(store.ensure_default(name))
        return channels

    def get_channel(self, name: str) -> Channel:
        paths = self._paths()
        store = ChannelStore(paths)
        folder = name.strip()
        library = paths.library_dir(folder)
        if not library.is_dir():
            raise FileNotFoundError(f"Channel library folder not found: {folder}")
        return store.ensure_default(folder)

    def create_channel(self, name: str) -> Channel:
        folder_name = self._validate_name(name)
        paths = self._paths()
        store = ChannelStore(paths)

        library = paths.library_dir(folder_name)
        library.mkdir(parents=True, exist_ok=True)

        if store.exists(folder_name):
            return store.load(folder_name)

        channel = Channel.create_default(folder_name)
        store.save(channel)
        return store.ensure_default(folder_name)

    def select_channel(self, name: str) -> Channel:
        channel = self.get_channel(name)
        self._active_folder_name = channel.folder_name
        return channel

    def save_channel(self, channel: Channel) -> Channel:
        """Persist channel configuration (including narrator preferences)."""
        paths = self._paths()
        store = ChannelStore(paths)
        store.save(channel)
        return channel

    def _validate_name(self, name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Channel name cannot be empty.")
        if cleaned in {".", ".."}:
            raise ValueError("Channel name is invalid.")
        if _INVALID_NAME.search(cleaned):
            raise ValueError("Channel name contains invalid characters.")
        if cleaned.startswith("."):
            raise ValueError("Channel name cannot start with a dot.")
        return cleaned
