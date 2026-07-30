"""Output naming and folder resolution for thumbnails."""

from __future__ import annotations

from pathlib import Path

THUMBNAIL_FOLDER = "thumbnail"
THUMBNAIL_BASENAME = "thumbnail.png"
MANIFEST_BASENAME = "thumbnail_manifest.json"


def thumbnail_basename() -> str:
    return THUMBNAIL_BASENAME


def manifest_basename() -> str:
    return MANIFEST_BASENAME


def resolve_thumbnail_dir(project_dir: Path) -> Path:
    folder = project_dir.expanduser().resolve() / THUMBNAIL_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def thumbnail_path(project_dir: Path) -> Path:
    """Canonical exported thumbnail — ``thumbnail/thumbnail.png``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_BASENAME


def thumbnail_manifest_path(project_dir: Path) -> Path:
    """Sidecar plan written beside the final thumbnail."""
    return resolve_thumbnail_dir(project_dir) / MANIFEST_BASENAME
