"""Path helpers for projects under Project Root / channel."""

from __future__ import annotations

from pathlib import Path

CONFIG_FILENAME = "project.json"


class ProjectPaths:
    """Resolves project directories inside a channel library folder."""

    def __init__(self, project_root: Path, channel_name: str) -> None:
        self._project_root = project_root.expanduser().resolve()
        self._channel_name = channel_name

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def channel_name(self) -> str:
        return self._channel_name

    @property
    def channel_dir(self) -> Path:
        return self._project_root / self._channel_name

    def project_dir(self, folder_name: str) -> Path:
        return self.channel_dir / folder_name

    def config_file(self, folder_name: str) -> Path:
        return self.project_dir(folder_name) / CONFIG_FILENAME
