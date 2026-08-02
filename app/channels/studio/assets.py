"""Install named assets into a channel studio folder (portable relative paths)."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.channels.studio.paths import BRANDING_DIR, branding_dir, channel_studio_dir

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".bmp"}
_VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}
_ALLOWED_SUFFIXES = _IMAGE_SUFFIXES | _VIDEO_SUFFIXES


def is_image_path(path: Path) -> bool:
    return path.suffix.casefold() in _IMAGE_SUFFIXES


def is_video_path(path: Path) -> bool:
    return path.suffix.casefold() in _VIDEO_SUFFIXES


def resolve_studio_asset(data_root: Path, folder_name: str, stored: str) -> Path | None:
    """Resolve a stored relative/absolute asset path under the channel studio."""
    raw = (stored or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_file():
        return path.resolve()
    candidate = channel_studio_dir(data_root, folder_name) / path
    if candidate.is_file():
        return candidate.resolve()
    return None


def install_named_asset(
    data_root: Path,
    folder_name: str,
    *,
    asset_key: str,
    source: Path,
    subdir: str = BRANDING_DIR,
) -> str:
    """Copy source into channels/<folder>/<subdir>/<asset_key><ext>.

    Returns a portable relative path (e.g. branding/logo.png).
    Replaces any previous file with the same asset_key stem.
    """
    src = Path(source)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    suffix = src.suffix.casefold()
    if suffix not in _ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported file type: {suffix or '(none)'}")

    key = _safe_asset_key(asset_key)
    if subdir == BRANDING_DIR:
        dest_dir = branding_dir(data_root, folder_name)
    else:
        dest_dir = channel_studio_dir(data_root, folder_name) / subdir.strip()
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Remove previous variants of this asset key (logo.png vs logo.webp).
    for existing in dest_dir.glob(f"{key}.*"):
        if existing.is_file():
            existing.unlink(missing_ok=True)

    dest = dest_dir / f"{key}{suffix}"
    shutil.copy2(src, dest)
    return f"{subdir.strip('/')}/{dest.name}"


def remove_named_asset(
    data_root: Path,
    folder_name: str,
    stored: str,
    *,
    asset_key: str = "",
    subdir: str = BRANDING_DIR,
) -> None:
    """Delete a local studio asset if it lives inside the channel folder."""
    resolved = resolve_studio_asset(data_root, folder_name, stored)
    root = channel_studio_dir(data_root, folder_name).resolve()
    if resolved is not None:
        try:
            resolved.relative_to(root)
        except ValueError:
            resolved = None
        else:
            if resolved.is_file():
                resolved.unlink(missing_ok=True)

    if asset_key:
        key = _safe_asset_key(asset_key)
        if subdir == BRANDING_DIR:
            dest_dir = branding_dir(data_root, folder_name)
        else:
            dest_dir = channel_studio_dir(data_root, folder_name) / subdir.strip()
        if dest_dir.is_dir():
            for existing in dest_dir.glob(f"{key}.*"):
                if existing.is_file():
                    existing.unlink(missing_ok=True)


def _safe_asset_key(asset_key: str) -> str:
    key = (asset_key or "asset").strip().replace(" ", "_")
    cleaned = "".join(ch for ch in key if ch.isalnum() or ch in {"_", "-"})
    return cleaned or "asset"
