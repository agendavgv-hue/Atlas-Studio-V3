"""Paths for Channel Studio packs beside channel.json."""

from __future__ import annotations

from pathlib import Path

from app.core.storage_paths import StoragePaths

GENERAL_FILE = "studio_general.json"
BRAND_KIT_FILE = "brand_kit.json"
THUMBNAIL_SETTINGS_FILE = "thumbnail_studio.json"
THUMBNAIL_DNA_FILE = "thumbnail_dna.json"
IMAGE_SETTINGS_FILE = "image_studio.json"
IMAGE_DNA_FILE = "image_dna.json"
MOVIE_DNA_FILE = "movie_dna.json"
STORY_DNA_FILE = "story_dna.json"
VOICE_DNA_FILE = "voice_dna.json"
MUSIC_DNA_FILE = "music_dna.json"
CREATIVE_RULES_FILE = "creative_rules.json"
GOALS_FILE = "goals.json"
PERSONALITY_FILE = "personality.json"
REFERENCES_DIR = "references"
BRANDING_DIR = "branding"

REFERENCE_KINDS: tuple[str, ...] = (
    "thumbnails",
    "images",
    "movies",
    "voices",
    "music",
    "branding",
)


def channel_studio_dir(data_root: Path, folder_name: str) -> Path:
    return StoragePaths(data_root).channels / folder_name.strip()


def branding_dir(data_root: Path, folder_name: str) -> Path:
    """Named Brand Kit assets — channels/<folder>/branding/."""
    return channel_studio_dir(data_root, folder_name) / BRANDING_DIR


def references_root(data_root: Path, folder_name: str) -> Path:
    return channel_studio_dir(data_root, folder_name) / REFERENCES_DIR


def reference_kind_dir(data_root: Path, folder_name: str, kind: str) -> Path:
    key = (kind or "").strip().casefold()
    if key not in REFERENCE_KINDS:
        raise ValueError(f"Unknown reference kind: {kind}")
    return references_root(data_root, folder_name) / key
