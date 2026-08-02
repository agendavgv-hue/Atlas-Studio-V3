"""Persist and load per-channel Thumbnail DNA."""

from __future__ import annotations

import json
from pathlib import Path

from app.channels.channel_ids import channel_id
from app.core.storage_paths import StoragePaths
from app.models.thumbnail_dna import ThumbnailDNA

DNA_FILENAME = "thumbnail_dna.json"
MAX_REFERENCES = 10


class ThumbnailDNAService:
    """Read/write ``thumbnail_dna.json`` under Cache/thumbnails/<channel_id>/."""

    def __init__(self, data_root: Path) -> None:
        self._paths = StoragePaths(data_root)

    def channel_dir(self, channel: str) -> Path:
        cid = channel_id(channel)
        path = self._paths.cache / "thumbnails" / cid
        path.mkdir(parents=True, exist_ok=True)
        return path

    def dna_path(self, channel: str) -> Path:
        return self.channel_dir(channel) / DNA_FILENAME

    def get_thumbnail_dna(self, channel: str) -> ThumbnailDNA | None:
        path = self.dna_path(channel)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        dna = ThumbnailDNA.from_dict(raw)
        if not dna.channel_id:
            dna.channel_id = channel_id(channel)
        if not dna.channel_name:
            dna.channel_name = channel.strip()
        return dna

    def save_thumbnail_dna(self, channel: str, dna: ThumbnailDNA) -> Path:
        cid = channel_id(channel)
        dna.channel_id = cid
        dna.channel_name = (channel or "").strip() or dna.channel_name
        path = self.dna_path(channel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dna.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    def clear_thumbnail_dna(self, channel: str) -> None:
        path = self.dna_path(channel)
        if path.is_file():
            path.unlink()
