"""ShortsManifest — durable production plan for one or more shorts.

Written as ``short/shorts_manifest.json``. Holds a collection of
``ShortsDefinition`` entries (never a single-video-only schema).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.shorts.definition import ShortsDefinition
from app.shorts.naming import SHORTS_FOLDER


MANIFEST_VERSION = 1


@dataclass
class ShortsManifest:
    """Complete durable plan for a Shorts run."""

    version: int = MANIFEST_VERSION
    definitions: list[ShortsDefinition] = field(default_factory=list)
    selection_source: str = ""  # production_sheet | images_fallback
    folder: str = SHORTS_FOLDER
    rationale: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.definitions)

    def definition_by_id(self, definition_id: str) -> ShortsDefinition | None:
        for item in self.definitions:
            if item.definition_id == definition_id:
                return item
        return None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_definitions(
        cls,
        definitions: list[ShortsDefinition],
        *,
        selection_source: str = "",
        rationale: str = "",
    ) -> ShortsManifest:
        return cls(
            definitions=list(definitions),
            selection_source=selection_source,
            rationale=rationale,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShortsManifest:
        raw = dict(data or {})
        definitions = [
            ShortsDefinition.from_dict(item)
            for item in (raw.get("definitions") or [])
            if isinstance(item, dict)
        ]
        return cls(
            version=int(raw.get("version") or MANIFEST_VERSION),
            definitions=definitions,
            selection_source=str(raw.get("selection_source") or ""),
            folder=str(raw.get("folder") or SHORTS_FOLDER),
            rationale=str(raw.get("rationale") or ""),
            extras=dict(raw.get("extras") or {}),
        )

    @classmethod
    def read_json(cls, path: Path) -> ShortsManifest:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
