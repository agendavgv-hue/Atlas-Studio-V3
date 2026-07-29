"""Scan a project directory and report progress. No UI coupling."""

from __future__ import annotations

from pathlib import Path

from app.artifacts import ArtifactKind, ArtifactResolver
from app.artifacts.rules import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from app.projects.project_status import (
    PROGRESS_STEP_DEFINITIONS,
    ProgressStep,
    ProjectProgress,
)

_IGNORE_FILES = {"thumbs.db", "desktop.ini", ".ds_store"}


def scan_project_progress(project_dir: Path) -> ProjectProgress:
    """Analyse project folders and return completion for each progress step."""
    root = project_dir.expanduser().resolve()
    resolver = ArtifactResolver(root)
    completed = {
        "script": resolver.exists(ArtifactKind.SCRIPT),
        "production_sheet": resolver.exists(ArtifactKind.PRODUCTION_SHEET),
        "images": resolver.exists(ArtifactKind.IMAGES),
        "voice": resolver.exists(ArtifactKind.VOICE),
        "instagram": _has_media(root / "insta", IMAGE_EXTENSIONS),
        # Movie is complete when the final export exists, or kept scene renders remain.
        "movie": resolver.exists(ArtifactKind.YOUTUBE_EXPORT)
        or _has_movie_working_files(root / "mp4"),
        "shorts": _has_media(root / "short", VIDEO_EXTENSIONS),
        "thumbnail": resolver.exists(ArtifactKind.THUMBNAIL),
        "youtube_export": resolver.exists(ArtifactKind.YOUTUBE_EXPORT),
    }
    steps = tuple(
        ProgressStep(key=key, label=label, complete=completed[key])
        for key, label in PROGRESS_STEP_DEFINITIONS
    )
    return ProjectProgress(steps=steps)


def _iter_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    files: list[Path] = []
    for entry in folder.iterdir():
        if not entry.is_file():
            continue
        if entry.name.startswith("."):
            continue
        if entry.name.casefold() in _IGNORE_FILES:
            continue
        files.append(entry)
    return files


def _has_media(folder: Path, extensions: frozenset[str] | set[str]) -> bool:
    return any(path.suffix.casefold() in extensions for path in _iter_files(folder))


def _has_movie_working_files(folder: Path) -> bool:
    """True when kept scene renders exist (ignores temporary .atlas_render work)."""
    if not folder.is_dir():
        return False
    for path in _iter_files(folder):
        if path.suffix.casefold() in VIDEO_EXTENSIONS:
            return True
    return False
