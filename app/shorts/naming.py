"""Output naming and folder resolution for Shorts.

Uses the existing project template folder ``short/`` so Project Intelligence
detects completed shorts without Resolver/PI changes.
"""

from __future__ import annotations

from pathlib import Path

SHORTS_FOLDER = "short"
MANIFEST_BASENAME = "shorts_manifest.json"


def short_basename(index: int) -> str:
    """1-based index → ``short_01.mp4``."""
    if index < 1:
        raise ValueError("Short index must be 1-based.")
    return f"short_{index:02d}.mp4"


def manifest_basename() -> str:
    return MANIFEST_BASENAME


def resolve_shorts_dir(project_dir: Path) -> Path:
    folder = project_dir.expanduser().resolve() / SHORTS_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def short_path(project_dir: Path, index: int) -> Path:
    """Canonical path for one exported short."""
    return resolve_shorts_dir(project_dir) / short_basename(index)


def shorts_manifest_path(project_dir: Path) -> Path:
    """Durable plan written beside exported shorts."""
    return resolve_shorts_dir(project_dir) / MANIFEST_BASENAME
