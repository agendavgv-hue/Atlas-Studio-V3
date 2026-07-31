"""Compatibility re-export — prefer ``thumbnail_director`` for new imports."""

from app.thumbnail.thumbnail_director import (  # noqa: F401
    ALLOWED_EMOTIONS,
    ThumbnailDirector,
    ThumbnailStrategy,
)

__all__ = ["ALLOWED_EMOTIONS", "ThumbnailDirector", "ThumbnailStrategy"]
