"""Standard image output names and folder resolution."""

from __future__ import annotations

from pathlib import Path

# V3 standard — never create the legacy singular name for new work.
IMAGES_FOLDER = "images"
LEGACY_IMAGES_FOLDER = "image"


def image_basename(index: int) -> str:
    """1-based index → ``image_01.png``."""
    if index < 1:
        raise ValueError("Image index must be 1-based.")
    return f"image_{index:02d}.png"


def resolve_images_dir(project_dir: Path) -> Path:
    """Resolve the project images folder with V2/V3 compatibility.

    Rules:
    - If ``images/`` exists → use it
    - Else if ``image/`` exists → use it (legacy V2)
    - Else → create ``images/`` (never create ``image/``)
    """
    root = project_dir.expanduser().resolve()
    standard = root / IMAGES_FOLDER
    legacy = root / LEGACY_IMAGES_FOLDER
    if standard.is_dir():
        return standard
    if legacy.is_dir():
        return legacy
    standard.mkdir(parents=True, exist_ok=True)
    return standard
