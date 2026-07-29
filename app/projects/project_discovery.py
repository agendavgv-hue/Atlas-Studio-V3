"""Discover project folders inside a channel library directory."""

from __future__ import annotations

from pathlib import Path


def discover_project_folder_names(channel_dir: Path) -> list[str]:
    """Return sorted names of immediate project subdirectories."""
    root = channel_dir.expanduser().resolve()
    if not root.is_dir():
        return []

    names: list[str] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if name.startswith("."):
            continue
        if name.lower() in {"thumbs.db", "desktop.ini"}:
            continue
        names.append(name)

    return sorted(names, key=str.casefold)
