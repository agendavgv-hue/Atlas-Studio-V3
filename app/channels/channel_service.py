"""Channel application service — create, list, and load channels."""

from __future__ import annotations

import re
from pathlib import Path

from app.channels.channel_discovery import discover_channel_folder_names
from app.channels.channel_paths import ChannelPaths
from app.channels.channel_profile_store import ChannelProfilePackStore
from app.channels.channel_store import ChannelStore
from app.channels.generated_profile import GeneratedChannelProfile
from app.channels.models import Channel
from app.channels.reference_channels import (
    assert_not_reference_channel,
    is_reference_channel,
)
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
        self._list_cache: tuple[float, list[Channel]] | None = None
        self._list_cache_ttl_s = 2.0

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
        self.invalidate_list_cache()
        return resolved

    def invalidate_list_cache(self) -> None:
        """Drop cached channel listings (call after create / root change)."""
        self._list_cache = None

    def _paths(self) -> ChannelPaths:
        root = require_project_root(self._config.project_root)
        return ChannelPaths(self._storage, root)

    def list_channels(self) -> list[Channel]:
        """Discover library folders and ensure each has Atlas config."""
        import time

        now = time.monotonic()
        cached = self._list_cache
        if cached is not None and (now - cached[0]) < self._list_cache_ttl_s:
            return list(cached[1])

        try:
            paths = self._paths()
        except ProjectRootError:
            return []

        store = ChannelStore(paths)
        channels: list[Channel] = []
        for name in discover_channel_folder_names(paths.project_root):
            channels.append(store.ensure_default(name))
        self._list_cache = (now, list(channels))
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
        created = store.ensure_default(folder_name)
        self._ensure_channel_brain(created)
        self._ensure_creative_director(created)
        self._ensure_channel_studio(created)
        self.invalidate_list_cache()
        return created

    def create_channel_from_profile(self, profile: GeneratedChannelProfile) -> Channel:
        """Create a NEW channel from AI Channel Creator DNA.

        Refuses official reference channels (Hollow Atlas / Mirror Drift).
        """
        folder_name = self._validate_name(profile.name)
        assert_not_reference_channel(folder_name, action="create")
        paths = self._paths()
        store = ChannelStore(paths)

        if store.exists(folder_name) or paths.library_dir(folder_name).is_dir():
            raise ValueError(
                f"Channel '{folder_name}' already exists. "
                "AI Channel Creator only creates NEW channels."
            )

        library = paths.library_dir(folder_name)
        library.mkdir(parents=True, exist_ok=True)

        channel = Channel.create_default(folder_name)
        fields = profile.to_channel_fields()
        channel.description = str(fields.get("description") or "")
        channel.image_prompt = str(fields.get("image_prompt") or "")
        channel.negative_prompt = str(fields.get("negative_prompt") or "")
        channel.thumbnail_prompt = str(fields.get("thumbnail_prompt") or "")
        channel.outro_line = str(fields.get("outro_line") or "").strip()
        channel.voice = dict(fields.get("voice") or {})
        store.save(channel)

        packs = ChannelProfilePackStore(self._config.data_root)
        if profile.dna:
            packs.upsert_dna(folder_name, profile.dna)
        if profile.style:
            packs.upsert_style(folder_name, profile.style)

        created = store.ensure_default(folder_name)
        self._ensure_channel_brain(created)
        self._ensure_creative_director(created)
        self._ensure_channel_studio(created)
        self.invalidate_list_cache()
        return created

    def select_channel(self, name: str) -> Channel:
        channel = self.get_channel(name)
        self._active_folder_name = channel.folder_name
        return channel

    def save_channel(self, channel: Channel) -> Channel:
        """Persist channel configuration (including narrator preferences).

        Reference channels may still update voice prefs; DNA/style packs for
        Hollow Atlas / Mirror Drift are never rewritten by AI Channel Creator.
        """
        paths = self._paths()
        store = ChannelStore(paths)
        # Guard: never blank out reference channel identity fields via empty saves.
        if is_reference_channel(channel.folder_name) and store.exists(channel.folder_name):
            existing = store.load(channel.folder_name)
            if not (channel.image_prompt or "").strip():
                channel.image_prompt = existing.image_prompt
            if not (channel.negative_prompt or "").strip():
                channel.negative_prompt = existing.negative_prompt
            if not (channel.outro_line or "").strip():
                channel.outro_line = existing.outro_line
        store.save(channel)
        self._ensure_channel_brain(channel)
        self._ensure_creative_director(channel)
        self._ensure_channel_studio(channel)
        return channel

    def _ensure_channel_brain(self, channel: Channel) -> None:
        """Create Channel Brain pack if missing (never fails channel create)."""
        try:
            from app.brain.service import ChannelBrainService
            from app.services.thumbnail_dna_service import ThumbnailDNAService
            from app.thumbnail.dna_loader import ChannelDNALoader

            brains = ChannelBrainService(self._config.data_root)
            learned = ThumbnailDNAService(self._config.data_root).get_thumbnail_dna(
                channel.folder_name
            )
            pack = None
            try:
                pack = ChannelDNALoader(data_root=self._config.data_root).get_dna(
                    channel.folder_name
                )
            except Exception:  # noqa: BLE001
                pack = None
            brains.ensure_brain(
                channel.folder_name,
                source=channel,
                learned_thumbnail=learned,
                channel_pack=pack,
            )
        except Exception:  # noqa: BLE001
            return

    def _ensure_creative_director(self, channel: Channel) -> None:
        """Create Creative Director pack if missing (never fails channel create)."""
        try:
            from app.brain.service import ChannelBrainService
            from app.creative.services.director_service import CreativeDirectorService

            brains = ChannelBrainService(self._config.data_root)
            brain = None
            if brains.exists(channel.folder_name):
                brain = brains.load(channel.folder_name)
            CreativeDirectorService(self._config.data_root).ensure(
                channel.folder_name,
                source=channel,
                brain=brain,
            )
        except Exception:  # noqa: BLE001
            return

    def _ensure_channel_studio(self, channel: Channel) -> None:
        """Create Channel Studio pack if missing (never fails channel create)."""
        try:
            from app.channels.studio.service import ChannelStudioService

            ChannelStudioService(self._config.data_root).ensure(
                channel.folder_name,
                channel=channel,
            )
        except Exception:  # noqa: BLE001
            return

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
