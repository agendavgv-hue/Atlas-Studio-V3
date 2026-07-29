"""Application configuration persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths


CONFIG_FILENAME = "config.json"


def default_data_root() -> Path:
    """Atlas Studio data root (parent of the ``app`` package)."""
    return Path(__file__).resolve().parents[2]


def bootstrap_config_path() -> Path:
    """Platform user-config location for Atlas Studio settings."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return Path(base) / CONFIG_FILENAME


@dataclass
class AppConfig:
    """Persisted application settings.

    Bootstrap config lives in the platform user-config directory so roots
    can be changed safely.

    ``data_root`` — Atlas Studio application data
    ``project_root`` — user YouTube library (optional until set in Settings)
    """

    data_root: Path
    project_root: Path | None = None

    @classmethod
    def load(cls, default_root: Path | None = None) -> AppConfig:
        root_fallback = (default_root or default_data_root()).resolve()
        path = bootstrap_config_path()
        if not path.is_file():
            return cls(data_root=root_fallback, project_root=None)

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(data_root=root_fallback, project_root=None)

        stored = raw.get("data_root")
        data_root = (
            Path(stored).expanduser().resolve()
            if stored and isinstance(stored, str)
            else root_fallback
        )

        project_raw = raw.get("project_root")
        project_root: Path | None = None
        if project_raw and isinstance(project_raw, str):
            project_root = Path(project_raw).expanduser().resolve()

        return cls(data_root=data_root, project_root=project_root)

    def save(self) -> None:
        path = bootstrap_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, str | None] = {
            "data_root": str(self.data_root.resolve()),
            "project_root": (
                str(self.project_root.resolve()) if self.project_root is not None else None
            ),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
