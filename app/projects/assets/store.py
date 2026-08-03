"""Persist assets.json beside project.json."""

from __future__ import annotations

import json
from pathlib import Path

from app.projects.assets.models import AssetCatalog

ASSETS_FILENAME = "assets.json"


def assets_path(project_dir: Path) -> Path:
    return project_dir.expanduser().resolve() / ASSETS_FILENAME


class AssetStore:
    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir.expanduser().resolve()
        self._path = assets_path(self._project_dir)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AssetCatalog:
        if not self._path.is_file():
            return AssetCatalog()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AssetCatalog()
        if not isinstance(raw, dict):
            return AssetCatalog()
        return AssetCatalog.from_dict(raw)

    def save(self, catalog: AssetCatalog) -> Path:
        self._project_dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(catalog.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path
