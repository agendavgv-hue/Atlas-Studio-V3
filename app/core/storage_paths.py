"""Resolve Atlas Studio storage directories from a data root."""

from __future__ import annotations

from pathlib import Path


# Single source of truth for top-level directory names (Blueprint layout).
CHANNELS = "Channels"
PROJECTS = "Projects"
ASSETS = "Assets"
CACHE = "Cache"
BRAIN = "Brain"
CREATIVE = "Creative"
EXPORTS = "Exports"
LOGS = "Logs"
VOICES = "voices"

MANAGED_DIRECTORIES: tuple[str, ...] = (
    CHANNELS,
    PROJECTS,
    ASSETS,
    CACHE,
    BRAIN,
    CREATIVE,
    EXPORTS,
    LOGS,
    VOICES,
)


class StoragePaths:
    """Path resolver for the Atlas Studio data root and its children."""

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def channels(self) -> Path:
        return self._root / CHANNELS

    @property
    def projects(self) -> Path:
        return self._root / PROJECTS

    @property
    def assets(self) -> Path:
        return self._root / ASSETS

    @property
    def cache(self) -> Path:
        return self._root / CACHE

    @property
    def voices(self) -> Path:
        """Local TTS voice model packs (e.g. ``voices/piper``)."""
        return self._root / VOICES

    @property
    def brain(self) -> Path:
        """Channel Brain roots — durable per-channel identity + memory."""
        return self._root / BRAIN

    @property
    def creative(self) -> Path:
        """Creative Director roots — brand, style, references, rules."""
        return self._root / CREATIVE

    @property
    def exports(self) -> Path:
        return self._root / EXPORTS

    @property
    def logs(self) -> Path:
        return self._root / LOGS

    def all_directories(self) -> tuple[Path, ...]:
        return tuple(self._root / name for name in MANAGED_DIRECTORIES)
