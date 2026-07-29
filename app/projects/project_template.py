"""Standard project folder template."""

from __future__ import annotations

from pathlib import Path

# Single source of truth for new-project layout (V3 standard).
PROJECT_TEMPLATE_FOLDERS: tuple[str, ...] = (
    "audio",
    "ffmpeg",
    "input",
    "mp3",
    "script",
    "images",
    "insta",
    "mp4",
    "short",
    "thumbnail",
    "youtube_video",
)


def ensure_project_template(project_dir: Path) -> None:
    """Create any missing template folders. Never deletes existing content."""
    root = project_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in PROJECT_TEMPLATE_FOLDERS:
        (root / name).mkdir(parents=True, exist_ok=True)
