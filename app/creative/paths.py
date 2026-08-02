"""Filesystem layout for per-channel Creative Director packs."""

from __future__ import annotations

from pathlib import Path

from app.channels.channel_ids import channel_id
from app.core.storage_paths import StoragePaths

DIRECTOR_FILE = "director.json"
BRAND_KIT_FILE = "brand_kit.json"
STYLE_LIBRARY_FILE = "style_library.json"
REFERENCES_DIR = "references"

REFERENCE_KINDS: tuple[str, ...] = (
    "thumbnails",
    "images",
    "movies",
    "intros",
    "outros",
    "animations",
    "voices",
    "music",
    "logo",
    "banner",
    "brand",
)


def creative_root(data_root: Path) -> Path:
    return StoragePaths(data_root).creative


def channel_creative_dir(data_root: Path, channel: str) -> Path:
    return creative_root(data_root) / channel_id(channel)


def references_dir(data_root: Path, channel: str) -> Path:
    return channel_creative_dir(data_root, channel) / REFERENCES_DIR


def reference_kind_dir(data_root: Path, channel: str, kind: str) -> Path:
    key = (kind or "").strip().casefold()
    if key not in REFERENCE_KINDS:
        raise ValueError(
            f"Unknown reference kind '{kind}'. "
            f"Expected one of: {', '.join(REFERENCE_KINDS)}"
        )
    return references_dir(data_root, channel) / key
