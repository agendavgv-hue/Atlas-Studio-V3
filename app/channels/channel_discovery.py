"""Discover existing channel folders inside the Project Root."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

# Single configurable default ignore list for Project Root scanning.
# Callers may pass a custom iterable to discover_channel_folder_names.
DEFAULT_IGNORED_CHANNEL_FOLDERS: tuple[str, ...] = ("MASTER",)


def _ignored_name_set(ignored_folders: Iterable[str] | None) -> set[str]:
    folders = (
        DEFAULT_IGNORED_CHANNEL_FOLDERS
        if ignored_folders is None
        else tuple(ignored_folders)
    )
    return {name.casefold() for name in folders}


def discover_channel_folder_names(
    project_root: Path,
    ignored_folders: Iterable[str] | None = None,
) -> list[str]:
    """Return sorted names of immediate subdirectories in the Project Root.

    Skips hidden/system entries and names in the ignore list.
    Does not hardcode channel names.
    """
    root = project_root.expanduser().resolve()
    if not root.is_dir():
        return []

    ignored = _ignored_name_set(ignored_folders)
    names: list[str] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if name.startswith("."):
            continue
        if name.lower() in {"thumbs.db", "desktop.ini"}:
            continue
        if name.casefold() in ignored:
            continue
        names.append(name)

    return sorted(names, key=str.casefold)
