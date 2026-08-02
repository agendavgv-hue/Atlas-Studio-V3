"""Critic domain identifiers — generators call Critic with one of these."""

from __future__ import annotations

from enum import Enum


class CriticDomain(str, Enum):
    SCRIPT = "script"
    PRODUCTION_SHEET = "production_sheet"
    IMAGE = "image"
    THUMBNAIL = "thumbnail"
    MOVIE = "movie"
    VOICE = "voice"
    SEO = "seo"
    SHORT = "short"
    INTRO = "intro"
    OUTRO = "outro"

    @classmethod
    def parse(cls, value: str) -> CriticDomain:
        key = (value or "").strip().casefold().replace(" ", "_").replace("-", "_")
        aliases = {
            "sheet": cls.PRODUCTION_SHEET,
            "production": cls.PRODUCTION_SHEET,
            "images": cls.IMAGE,
            "thumb": cls.THUMBNAIL,
            "video": cls.MOVIE,
            "render": cls.MOVIE,
            "shorts": cls.SHORT,
            "narration": cls.VOICE,
        }
        if key in aliases:
            return aliases[key]
        for item in cls:
            if item.value == key:
                return item
        raise ValueError(f"Unknown critic domain: {value}")
