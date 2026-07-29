"""Path helpers for channel library folders and Atlas config packages."""

from __future__ import annotations

from pathlib import Path

from app.core.storage import Storage

CONFIG_FILENAME = "channel.json"


class ChannelPaths:
    """Resolves channel paths from Project Root + Atlas storage.

    Contains no Project-entity logic.
    """

    def __init__(self, storage: Storage, project_root: Path) -> None:
        self._storage = storage
        self._project_root = project_root.expanduser().resolve()

    @property
    def project_root(self) -> Path:
        return self._project_root

    def library_dir(self, folder_name: str) -> Path:
        return self._project_root / folder_name

    def config_dir(self, folder_name: str) -> Path:
        return self._storage.channels / folder_name

    def config_file(self, folder_name: str) -> Path:
        return self.config_dir(folder_name) / CONFIG_FILENAME
