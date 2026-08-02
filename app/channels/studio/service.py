"""ChannelStudioService — load/save channel identity packs (no AI)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.channels.models import Channel
from app.channels.studio.assets import (
    install_named_asset,
    remove_named_asset,
    resolve_studio_asset,
)
from app.channels.studio.models import ChannelStudioPack, StudioGeneral
from app.channels.studio.paths import BRANDING_DIR, branding_dir
from app.channels.studio.store import ChannelStudioStore
from app.channels.studio.sync import sync_studio_to_creative
from app.creative.models.rules import default_rules


class ChannelStudioService:
    """Authoritative Channel Studio config under Channels/<folder>/."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._store = ChannelStudioStore(self._data_root)

    @property
    def data_root(self) -> Path:
        return self._data_root

    def branding_path(self, folder_name: str) -> Path:
        path = branding_dir(self._data_root, folder_name)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def install_asset(
        self,
        folder_name: str,
        asset_key: str,
        source: Path,
        *,
        subdir: str = BRANDING_DIR,
    ) -> str:
        """Copy into channels/<folder>/<subdir>/ and return a relative path."""
        return install_named_asset(
            self._data_root,
            folder_name,
            asset_key=asset_key,
            source=source,
            subdir=subdir,
        )

    def install_brand_asset(self, folder_name: str, asset_key: str, source: Path) -> str:
        return self.install_asset(folder_name, asset_key, source, subdir=BRANDING_DIR)

    def remove_asset(
        self,
        folder_name: str,
        stored: str,
        *,
        asset_key: str = "",
        subdir: str = BRANDING_DIR,
    ) -> None:
        remove_named_asset(
            self._data_root,
            folder_name,
            stored,
            asset_key=asset_key,
            subdir=subdir,
        )

    def remove_brand_asset(
        self, folder_name: str, stored: str, *, asset_key: str = ""
    ) -> None:
        self.remove_asset(
            folder_name, stored, asset_key=asset_key, subdir=BRANDING_DIR
        )

    def resolve_asset(self, folder_name: str, stored: str) -> Path | None:
        return resolve_studio_asset(self._data_root, folder_name, stored)

    def load_basics(
        self, folder_name: str, *, channel: Channel | None = None
    ) -> ChannelStudioPack:
        """Fast open path — name, description, logo/brand only. No Creative sync."""
        pack = self._store.load_basics(folder_name)
        if channel is not None:
            if not pack.general.name:
                pack.general.name = channel.name
            if not pack.general.description:
                pack.general.description = channel.description
            if not pack.brand.logo and channel.logo:
                pack.brand.logo = channel.logo
            if not pack.brand.banner and channel.banner:
                pack.brand.banner = channel.banner
            if not pack.brand.outro and channel.outro_line:
                pack.brand.outro = channel.outro_line
                pack.brand.cta = channel.outro_line
        return pack

    def load_section(self, folder_name: str, section: str) -> Any:
        return self._store.load_section(folder_name, section)

    def apply_section(self, pack: ChannelStudioPack, section: str, payload: Any) -> None:
        self._store.apply_section(pack, section, payload)

    def hydrate_missing(self, pack: ChannelStudioPack, loaded: set[str]) -> None:
        """Fill unloaded sections from disk before a full save."""
        for key in (
            "general",
            "personality",
            "brand",
            "thumbnail",
            "image",
            "movie",
            "story",
            "voice",
            "music",
            "rules",
            "goals",
            "advanced",
        ):
            if key in loaded:
                continue
            self.apply_section(pack, key, self.load_section(pack.folder_name, key))

    def ensure(self, folder_name: str, *, channel: Channel | None = None) -> ChannelStudioPack:
        """Create/seed full pack (channel create path). Syncs Creative once."""
        pack = self._store.load(folder_name)
        if channel is not None:
            if not pack.general.name:
                pack.general.name = channel.name
            if not pack.general.description:
                pack.general.description = channel.description
            if not pack.brand.outro and channel.outro_line:
                pack.brand.outro = channel.outro_line
                pack.brand.cta = channel.outro_line
            if not pack.voice.voice and channel.voice:
                pack.voice.provider = str(channel.voice.get("provider") or pack.voice.provider)
                pack.voice.voice = str(
                    channel.voice.get("voice_name") or channel.voice.get("voice") or ""
                )
                pack.voice.voice_id = str(channel.voice.get("voice_id") or "")
                try:
                    pack.voice.speed = float(channel.voice.get("speed") or pack.voice.speed)
                except (TypeError, ValueError):
                    pass
        if not pack.rules:
            pack.rules = default_rules()
        self._store.save(pack)
        sync_studio_to_creative(self._data_root, pack)
        return pack

    def load(self, folder_name: str) -> ChannelStudioPack:
        return self._store.load(folder_name)

    def save(self, pack: ChannelStudioPack, *, channel: Channel | None = None) -> ChannelStudioPack:
        if not pack.general.name:
            pack.general.name = pack.folder_name
        self._store.save(pack)
        sync_studio_to_creative(self._data_root, pack)
        if channel is not None:
            self.apply_to_channel(pack, channel)
        return pack

    def apply_to_channel(self, pack: ChannelStudioPack, channel: Channel) -> Channel:
        """Mirror core fields into channel.json model (caller persists)."""
        channel.name = pack.general.name or channel.name
        channel.description = pack.general.description
        channel.logo = pack.brand.logo or channel.logo
        channel.banner = pack.brand.banner or channel.banner
        channel.outro_line = pack.brand.outro or pack.brand.cta or channel.outro_line
        channel.voice = {
            **dict(channel.voice or {}),
            "provider": pack.voice.provider,
            "voice_name": pack.voice.voice,
            "voice_id": pack.voice.voice_id,
            "speed": pack.voice.speed,
            "emotion": pack.voice.emotion,
        }
        return channel

    def reference_counts(self, folder_name: str) -> dict[str, int]:
        return self._store.reference_counts(folder_name)

    def list_references(self, folder_name: str, kind: str) -> list[Path]:
        return self._store.list_references(folder_name, kind)

    def add_reference(self, folder_name: str, kind: str, source: Path) -> Path:
        return self._store.add_reference(folder_name, kind, source)

    def delete_reference(self, folder_name: str, kind: str, target: Path) -> None:
        self._store.delete_reference(folder_name, kind, target)

    def seed_general_from_channel(self, channel: Channel) -> StudioGeneral:
        return StudioGeneral(
            name=channel.name,
            description=channel.description,
        )
