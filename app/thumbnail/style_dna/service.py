"""Thumbnail Style DNA service — train from Channel Studio references."""

from __future__ import annotations

from pathlib import Path

from app.channels.studio.paths import channel_studio_dir
from app.channels.studio.service import ChannelStudioService
from app.creative.engine.style_profile import StyleProfile
from app.thumbnail.style_dna.analyzer import ThumbnailStyleAnalyzer
from app.thumbnail.style_dna.models import ThumbnailStyleDNA
from app.thumbnail.style_dna.store import (
    STYLE_PROFILE_BASENAME,
    read_style_dna,
    write_style_dna,
)


class ThumbnailStyleDNAService:
    """Build/refresh Style DNA whenever reference thumbnails change."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._studio = ChannelStudioService(self._data_root)
        self._analyzer = ThumbnailStyleAnalyzer()

    def profile_path(self, folder_name: str) -> Path:
        return channel_studio_dir(self._data_root, folder_name) / STYLE_PROFILE_BASENAME

    def load(self, folder_name: str) -> ThumbnailStyleDNA | None:
        return read_style_dna(self.profile_path(folder_name))

    def ensure(self, folder_name: str, *, force: bool = False) -> ThumbnailStyleDNA:
        path = self.profile_path(folder_name)
        refs = self._studio.list_references(folder_name, "thumbnails")
        existing = read_style_dna(path)
        if (
            not force
            and existing is not None
            and existing.reference_count == len(refs)
            and (existing.reference_count > 0 or path.is_file())
            and existing.extras.get("style_dna_version") == 1
        ):
            return existing

        pack = self._studio.load_basics(folder_name)
        thumb = self._studio.load_section(folder_name, "thumbnail")
        hints = {
            "contrast": getattr(thumb, "contrast", "very_high"),
            "negative_space": getattr(thumb, "negative_space", "auto"),
            "emotion": getattr(thumb, "emotion", "curiosity"),
            "max_words": getattr(thumb, "max_words", 4),
            "logo_position": getattr(thumb, "logo_position", "auto"),
            "realism": getattr(thumb, "realism", 85.0),
            "mood": getattr(thumb, "emotion", "mystery"),
            "composition": getattr(thumb, "composition_style", "cinematic"),
            "brand_style": "premium_documentary",
            "atmosphere": "cinematic",
        }
        dna = self._analyzer.analyze(refs, studio_hints=hints)
        if not dna.dominant_colors:
            dna.dominant_colors = [
                c
                for c in (
                    pack.brand.primary_color,
                    pack.brand.secondary_color,
                    pack.brand.accent_color,
                )
                if c
            ]
        dna.extras["style_dna_version"] = 1
        dna.extras["folder_name"] = folder_name
        write_style_dna(path, dna)
        return dna

    def as_style_profile(self, dna: ThumbnailStyleDNA) -> StyleProfile:
        """Bridge to legacy StyleProfile consumers."""
        return StyleProfile(
            kind=dna.kind,
            reference_count=dna.reference_count,
            dominant_colors=list(dna.dominant_colors),
            contrast=dna.contrast,
            brightness=dna.brightness,
            color_temperature=dna.color_temperature,
            subject_bias=dna.subject_bias,
            negative_space=dna.negative_space,
            camera_angle=dna.camera_angle,
            atmosphere=dna.atmosphere,
            realism=dna.realism,
            mood=dna.mood,
            logo_bias=dna.logo_bias,
            average_words=dna.average_words,
            text_position=dna.text_position,
            notes=list(dna.notes),
        )
