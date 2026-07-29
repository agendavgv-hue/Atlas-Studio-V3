"""Output naming and folder resolution for movie renders."""

from __future__ import annotations

from pathlib import Path

MP4_FOLDER = "mp4"
YOUTUBE_FOLDER = "youtube_video"
FINAL_BASENAME = "video.mp4"
WORK_FOLDER = ".atlas_render"


def scene_basename(index: int) -> str:
    if index < 1:
        raise ValueError("Scene index must be 1-based.")
    return f"scene_{index:02d}.mp4"


def final_basename() -> str:
    return FINAL_BASENAME


def resolve_mp4_dir(project_dir: Path) -> Path:
    folder = project_dir.expanduser().resolve() / MP4_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def resolve_youtube_dir(project_dir: Path) -> Path:
    folder = project_dir.expanduser().resolve() / YOUTUBE_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def resolve_work_dir(project_dir: Path) -> Path:
    """Temporary working files when Keep Scene Renders is off."""
    folder = resolve_mp4_dir(project_dir) / WORK_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def final_video_path(project_dir: Path) -> Path:
    return resolve_youtube_dir(project_dir) / FINAL_BASENAME
