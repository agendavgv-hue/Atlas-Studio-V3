"""Application configuration persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths


CONFIG_FILENAME = "config.json"


def default_data_root() -> Path:
    """Project root (parent of the ``app`` package)."""
    return Path(__file__).resolve().parents[2]


def bootstrap_config_path() -> Path:
    """Platform user-config location for Atlas Studio settings."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return Path(base) / CONFIG_FILENAME


@dataclass
class AppConfig:
    """Persisted application settings.

    Bootstrap config lives in the platform user-config directory so the
    data root itself can be changed safely.
    """

    data_root: Path

    @classmethod
    def load(cls, default_root: Path | None = None) -> AppConfig:
        root_fallback = (default_root or default_data_root()).resolve()
        path = bootstrap_config_path()
        if not path.is_file():
            return cls(data_root=root_fallback)

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(data_root=root_fallback)

        stored = raw.get("data_root")
        if not stored or not isinstance(stored, str):
            return cls(data_root=root_fallback)

        return cls(data_root=Path(stored).expanduser().resolve())

    def save(self) -> None:
        path = bootstrap_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"data_root": str(self.data_root.resolve())}
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
