"""Artifact purpose kinds used across Atlas Studio."""

from __future__ import annotations

from enum import Enum


class ArtifactKind(str, Enum):
    SCRIPT = "script"
    PRODUCTION_SHEET = "production_sheet"
    IMAGES = "images"
    VOICE = "voice"
    THUMBNAIL = "thumbnail"
    YOUTUBE_EXPORT = "youtube_export"
