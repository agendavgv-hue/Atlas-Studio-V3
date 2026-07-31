"""Thumbnail domain — Intelligent Thumbnail Engine.

Script → Hero Subject → Hook → Channel Style → 4 variants.
Completely separate from the video Image Generator.
"""

from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.service import ThumbnailService

__all__ = ["ThumbnailMode", "ThumbnailService"]
