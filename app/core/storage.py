"""Storage façade for Atlas Studio data directories."""

from __future__ import annotations

from pathlib import Path

from app.core.app_config import AppConfig
from app.core.storage_paths import StoragePaths


def build_storage(default_root: Path | None = None) -> Storage:
    """Load config, create storage, and ensure the managed layout exists."""
    config = AppConfig.load(default_root=default_root)
    storage = Storage(config)
    storage.ensure_structure()
    return storage


class Storage:
    """Application-facing storage API.

    Future modules should use this object for all top-level data paths.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._paths = StoragePaths(config.data_root)

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def root(self) -> Path:
        return self._paths.root

    @property
    def channels(self) -> Path:
        return self._paths.channels

    @property
    def projects(self) -> Path:
        return self._paths.projects

    @property
    def assets(self) -> Path:
        return self._paths.assets

    @property
    def cache(self) -> Path:
        return self._paths.cache

    @property
    def brain(self) -> Path:
        return self._paths.brain

    @property
    def creative(self) -> Path:
        return self._paths.creative

    @property
    def exports(self) -> Path:
        return self._paths.exports

    @property
    def logs(self) -> Path:
        return self._paths.logs

    def ensure_structure(self) -> None:
        """Create the data root and managed directories if they are missing."""
        self.root.mkdir(parents=True, exist_ok=True)
        for directory in self._paths.all_directories():
            directory.mkdir(parents=True, exist_ok=True)

    def set_data_root(self, path: Path) -> None:
        """Update, persist, and ensure the storage layout at a new root."""
        self._config.data_root = path.expanduser().resolve()
        self._config.save()
        self._paths = StoragePaths(self._config.data_root)
        self.ensure_structure()
