"""Scan a project directory and report progress. No UI coupling."""

from __future__ import annotations

from pathlib import Path

from app.projects.project_status import (
    PROGRESS_STEP_DEFINITIONS,
    ProgressStep,
    ProjectProgress,
)

_SCRIPT_EXTENSIONS = {".txt", ".md", ".docx", ".rtf", ".doc"}
_SHEET_EXTENSIONS = {".csv", ".xlsx", ".xls", ".tsv", ".json"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

_SHEET_NAME_HINTS = ("production", "sheet", "scenes", "prod_sheet", "storyboard")

_IGNORE_FILES = {"thumbs.db", "desktop.ini", ".ds_store"}


def scan_project_progress(project_dir: Path) -> ProjectProgress:
    """Analyse project folders and return completion for each progress step."""
    root = project_dir.expanduser().resolve()
    completed = {
        "script": _has_script(root),
        "production_sheet": _has_production_sheet(root),
        "images": _has_images(root),
        "instagram": _has_media(root / "insta", _IMAGE_EXTENSIONS),
        "movie": _has_media(root / "mp4", _VIDEO_EXTENSIONS),
        "shorts": _has_media(root / "short", _VIDEO_EXTENSIONS),
        "thumbnail": _has_media(root / "thumbnail", _IMAGE_EXTENSIONS),
        "youtube_export": _has_media(root / "youtube_video", _VIDEO_EXTENSIONS),
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


def _has_media(folder: Path, extensions: set[str]) -> bool:
    return any(path.suffix.casefold() in extensions for path in _iter_files(folder))


def _is_production_sheet(path: Path) -> bool:
    name = path.stem.casefold()
    suffix = path.suffix.casefold()
    if suffix in _SHEET_EXTENSIONS:
        return True
    if suffix in _SCRIPT_EXTENSIONS and any(hint in name for hint in _SHEET_NAME_HINTS):
        return True
    return False


def _has_production_sheet(root: Path) -> bool:
    script_dir = root / "script"
    return any(_is_production_sheet(path) for path in _iter_files(script_dir))


def _has_script(root: Path) -> bool:
    script_dir = root / "script"
    for path in _iter_files(script_dir):
        if path.suffix.casefold() not in _SCRIPT_EXTENSIONS:
            continue
        if _is_production_sheet(path):
            continue
        return True
    return False


def _has_images(root: Path) -> bool:
    if _has_media(root / "images", _IMAGE_EXTENSIONS):
        return True
    # V2 tolerance: some projects used ``image`` instead of ``images``.
    return _has_media(root / "image", _IMAGE_EXTENSIONS)
