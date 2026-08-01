"""Persist per-channel DNA / style packs without mutating reference channels.

Writes only NEW channel entries into ``{data_root}/Assets/channel_*.json``.
Packaged Hollow Atlas / Mirror Drift entries are never copied or overwritten.
Loaders merge packaged base + Assets overlays so references stay authoritative.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.channels.reference_channels import (
    assert_not_reference_channel,
    is_reference_channel,
)
from app.core.storage_paths import StoragePaths


class ChannelProfilePackStore:
    """Append-only style/DNA pack writer for NEW channels."""

    def __init__(self, data_root: Path) -> None:
        self._paths = StoragePaths(data_root)

    @property
    def dna_path(self) -> Path:
        return self._paths.assets / "channel_dna.json"

    @property
    def style_path(self) -> Path:
        return self._paths.assets / "channel_style.json"

    def upsert_dna(self, channel_name: str, entry: dict[str, Any]) -> Path:
        assert_not_reference_channel(channel_name, action="write DNA for")
        return self._upsert(self.dna_path, channel_name, entry)

    def upsert_style(self, channel_name: str, entry: dict[str, Any]) -> Path:
        assert_not_reference_channel(channel_name, action="write style for")
        return self._upsert(self.style_path, channel_name, entry)

    def _upsert(
        self,
        target: Path,
        channel_name: str,
        entry: dict[str, Any],
    ) -> Path:
        payload = self._read_generated_only(target)
        payload[channel_name.strip()] = dict(entry or {})
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return target

    def _read_generated_only(self, target: Path) -> dict[str, Any]:
        """Load existing Assets packs, stripping any reference-channel keys."""
        if not target.is_file():
            return {}
        raw = self._read_object(target)
        return {
            str(key): value
            for key, value in raw.items()
            if not is_reference_channel(str(key)) and isinstance(value, dict)
        }

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return dict(raw) if isinstance(raw, dict) else {}
