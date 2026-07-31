"""Output naming and folder resolution for thumbnails."""

from __future__ import annotations

from pathlib import Path

THUMBNAIL_FOLDER = "thumbnail"
THUMBNAIL_BASENAME = "thumbnail.png"
THUMBNAIL_TITLE_BASENAME = "thumbnail_title.txt"
THUMBNAIL_PROMPT_BASENAME = "thumbnail_prompt.txt"
THUMBNAIL_STRATEGY_BASENAME = "thumbnail_strategy.json"
THUMBNAIL_MEMORY_BASENAME = "thumbnail_memory.json"
THUMBNAIL_CRITIQUE_BASENAME = "thumbnail_critique.json"
THUMBNAIL_QUALITY_BASENAME = "thumbnail_quality.json"
THUMBNAIL_HISTORY_BASENAME = "thumbnail_history.json"
THUMBNAIL_PROMPT_QUALITY_BASENAME = "thumbnail_prompt_quality.json"
MANIFEST_BASENAME = "thumbnail_manifest.json"

VARIANT_BASENAMES: dict[str, str] = {
    "A": "thumbnail_A_mystery.png",
    "B": "thumbnail_B_epic.png",
    "C": "thumbnail_C_documentary.png",
    "D": "thumbnail_D_dramatic.png",
}


def thumbnail_basename() -> str:
    return THUMBNAIL_BASENAME


def manifest_basename() -> str:
    return MANIFEST_BASENAME


def resolve_thumbnail_dir(project_dir: Path) -> Path:
    folder = project_dir.expanduser().resolve() / THUMBNAIL_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def thumbnail_path(project_dir: Path) -> Path:
    """Canonical primary thumbnail — ``thumbnail/thumbnail.png``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_BASENAME


def thumbnail_title_path(project_dir: Path) -> Path:
    """Curiosity hook text — ``thumbnail/thumbnail_title.txt``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_TITLE_BASENAME


def thumbnail_prompt_path(project_dir: Path) -> Path:
    """Primary image prompt — ``thumbnail/thumbnail_prompt.txt``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_PROMPT_BASENAME


def thumbnail_strategy_path(project_dir: Path) -> Path:
    """Creative strategy — ``thumbnail/thumbnail_strategy.json``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_STRATEGY_BASENAME


def thumbnail_memory_path(project_dir: Path) -> Path:
    """Learning memory — ``thumbnail/thumbnail_memory.json``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_MEMORY_BASENAME


def thumbnail_critique_path(project_dir: Path) -> Path:
    """Pre-generation critique report — ``thumbnail/thumbnail_critique.json``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_CRITIQUE_BASENAME


def thumbnail_quality_path(project_dir: Path) -> Path:
    """Final QA report — ``thumbnail/thumbnail_quality.json``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_QUALITY_BASENAME


def thumbnail_history_path(project_dir: Path) -> Path:
    """QA attempt history — ``thumbnail/thumbnail_history.json``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_HISTORY_BASENAME


def thumbnail_prompt_quality_path(project_dir: Path) -> Path:
    """Prompt craft score — ``thumbnail/thumbnail_prompt_quality.json``."""
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_PROMPT_QUALITY_BASENAME


def thumbnail_variant_path(project_dir: Path, variant_id: str) -> Path:
    name = VARIANT_BASENAMES.get(variant_id.upper(), f"thumbnail_{variant_id}.png")
    return resolve_thumbnail_dir(project_dir) / name


def thumbnail_manifest_path(project_dir: Path) -> Path:
    """Sidecar plan written beside the final thumbnail."""
    return resolve_thumbnail_dir(project_dir) / MANIFEST_BASENAME
