"""Discover existing channel folders inside the Project Root."""

from __future__ import annotations

from pathlib import Path


def discover_channel_folder_names(project_root: Path) -> list[str]:
    """Return sorted names of immediate subdirectories in the Project Root.

    Skips hidden/system entries. Does not hardcode channel names.
    """
    root = project_root.expanduser().resolve()
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
