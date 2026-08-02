"""Ensure Channel Studio reference style profiles exist and stay fresh."""

from __future__ import annotations

from pathlib import Path

from app.channels.studio.paths import channel_studio_dir
from app.channels.studio.service import ChannelStudioService
from app.creative.engine.style_profile import (
    StyleProfile,
    analyze_reference_images,
    load_style_profile,
    save_style_profile,
)

THUMBNAIL_STYLE_PROFILE_FILE = "thumbnail_style_profile.json"
IMAGE_STYLE_PROFILE_FILE = "image_style_profile.json"


class StyleProfileService:
    """Build/load thumbnail_style_profile.json + image_style_profile.json."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._studio = ChannelStudioService(self._data_root)

    def thumbnail_profile_path(self, folder_name: str) -> Path:
        return channel_studio_dir(self._data_root, folder_name) / THUMBNAIL_STYLE_PROFILE_FILE

    def image_profile_path(self, folder_name: str) -> Path:
        return channel_studio_dir(self._data_root, folder_name) / IMAGE_STYLE_PROFILE_FILE

    def ensure_thumbnail_profile(
        self, folder_name: str, *, force: bool = False
    ) -> StyleProfile:
        """Train complete Style DNA from ALL reference thumbnails, then expose StyleProfile."""
        from app.thumbnail.style_dna.service import ThumbnailStyleDNAService

        dna_service = ThumbnailStyleDNAService(self._data_root)
        dna = dna_service.ensure(folder_name, force=force)
        return dna_service.as_style_profile(dna)

    def ensure_image_profile(self, folder_name: str, *, force: bool = False) -> StyleProfile:
        path = self.image_profile_path(folder_name)
        refs = self._studio.list_references(folder_name, "images")
        existing = load_style_profile(path, kind="images")
        if (
            not force
            and existing is not None
            and existing.reference_count == len(refs)
            and (existing.reference_count > 0 or path.is_file())
        ):
            return existing

        image = self._studio.load_section(folder_name, "image")
        pack = self._studio.load_basics(folder_name)
        hints = {
            "atmosphere": getattr(image, "atmosphere", "none"),
            "mood": getattr(image, "mood", "mystery"),
            "realism": getattr(image, "realism", 90.0),
            "emotion": getattr(image, "mood", "mystery"),
        }
        profile = analyze_reference_images(refs, kind="images", studio_hints=hints)
        if not profile.dominant_colors:
            profile.dominant_colors = [
                c
                for c in (
                    pack.brand.primary_color,
                    pack.brand.secondary_color,
                    pack.brand.accent_color,
                )
                if c
            ]
        save_style_profile(path, profile)
        return profile
