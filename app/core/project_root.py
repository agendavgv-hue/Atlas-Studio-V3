"""User YouTube library (Project Root) helpers."""

from __future__ import annotations

from pathlib import Path


class ProjectRootError(ValueError):
    """Raised when the Project Root is missing or invalid."""


def is_project_root_configured(path: Path | None) -> bool:
    return path is not None


def require_project_root(path: Path | None) -> Path:
    """Return a usable Project Root or raise ``ProjectRootError``."""
    if path is None:
        raise ProjectRootError(
            "Project Root is not configured. Set it in Settings before managing channels."
        )
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise ProjectRootError(f"Project Root does not exist: {resolved}")
    if not resolved.is_dir():
        raise ProjectRootError(f"Project Root is not a directory: {resolved}")
    return resolved


def ensure_project_root(path: Path) -> Path:
    """Create the Project Root directory if needed and return it resolved."""
    resolved = path.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
