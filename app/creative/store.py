"""JSON persistence helpers for Creative packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_model(path: Path, factory: Callable[[dict[str, Any] | None], T]) -> T:
    return factory(read_json(path) or None)


def save_model(path: Path, model: Any) -> Path:
    return write_json(path, model.to_dict())
