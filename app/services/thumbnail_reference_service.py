"""ThumbnailReferenceService — import, manage, and analyze channel style refs."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.channels.channel_ids import channel_id
from app.models.thumbnail_dna import ThumbnailDNA
from app.services.thumbnail_dna_service import MAX_REFERENCES, ThumbnailDNAService
from app.services.thumbnail_style_analyzer import ThumbnailStyleAnalyzer

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


class ThumbnailReferenceService:
    """Per-channel reference thumbnails under Cache/thumbnails/<channel_id>/."""

    def __init__(
        self,
        data_root: Path,
        *,
        text_provider: Any | None = None,
        dna_service: ThumbnailDNAService | None = None,
        analyzer: ThumbnailStyleAnalyzer | None = None,
    ) -> None:
        self._data_root = Path(data_root)
        self._dna = dna_service or ThumbnailDNAService(self._data_root)
        self._analyzer = analyzer or ThumbnailStyleAnalyzer(text_provider)
        self._text = text_provider

    def set_text_provider(self, text_provider: Any | None) -> None:
        self._text = text_provider
        self._analyzer = ThumbnailStyleAnalyzer(text_provider)

    def channel_dir(self, channel: str) -> Path:
        return self._dna.channel_dir(channel)

    def load_references(self, channel: str) -> list[Path]:
        folder = self.channel_dir(channel)
        if not folder.is_dir():
            return []
        files = [
            p
            for p in folder.iterdir()
            if p.is_file()
            and p.suffix.casefold() in _IMAGE_SUFFIXES
            and p.name.casefold().startswith("ref_")
        ]
        return sorted(files, key=lambda p: p.name.casefold())

    def reference_count(self, channel: str) -> int:
        return len(self.load_references(channel))

    def save_reference(self, channel: str, source: Path) -> Path:
        """Import one image (max 10). Replaces oldest free slot or next index."""
        src = Path(source)
        if not src.is_file():
            raise FileNotFoundError(f"Reference image not found: {src}")
        if src.suffix.casefold() not in _IMAGE_SUFFIXES:
            raise ValueError(f"Unsupported image type: {src.suffix}")

        existing = self.load_references(channel)
        if len(existing) >= MAX_REFERENCES:
            raise ValueError(
                f"Maximum of {MAX_REFERENCES} reference thumbnails reached. "
                "Delete one before adding another."
            )

        folder = self.channel_dir(channel)
        index = self._next_index(existing)
        dest = folder / f"ref_{index:02d}{src.suffix.casefold()}"
        shutil.copy2(src, dest)
        self._mark_dirty(channel)
        return dest

    def replace_reference(self, channel: str, target: Path, source: Path) -> Path:
        src = Path(source)
        tgt = Path(target)
        if not src.is_file():
            raise FileNotFoundError(f"Replacement image not found: {src}")
        refs = {p.resolve() for p in self.load_references(channel)}
        if tgt.resolve() not in refs:
            raise FileNotFoundError(f"Reference not found for this channel: {tgt}")
        new_path = tgt.with_suffix(src.suffix.casefold())
        if new_path != tgt and new_path.exists():
            new_path.unlink()
        shutil.copy2(src, new_path)
        if new_path != tgt and tgt.exists():
            tgt.unlink()
        self._mark_dirty(channel)
        return new_path

    def delete_reference(self, channel: str, target: Path) -> None:
        tgt = Path(target)
        refs = {p.resolve() for p in self.load_references(channel)}
        if tgt.resolve() not in refs:
            raise FileNotFoundError(f"Reference not found for this channel: {tgt}")
        tgt.unlink(missing_ok=True)
        self._mark_dirty(channel)

    def analyze(self, channel: str) -> ThumbnailDNA:
        refs = self.load_references(channel)
        if not refs:
            raise ValueError("Upload at least one reference thumbnail before analyzing.")
        dna = self._analyzer.analyze(
            channel,
            refs,
            channel_id=channel_id(channel),
        )
        self._dna.save_thumbnail_dna(channel, dna)
        dirty = self.channel_dir(channel) / ".dna_stale"
        dirty.unlink(missing_ok=True)
        self._sync_brain_thumbnail_dna(channel, dna)
        return dna

    def get_thumbnail_dna(self, channel: str) -> ThumbnailDNA | None:
        return self._dna.get_thumbnail_dna(channel)

    def is_dna_stale(self, channel: str) -> bool:
        dirty = self.channel_dir(channel) / ".dna_stale"
        if dirty.is_file():
            return True
        if self.load_references(channel) and self.get_thumbnail_dna(channel) is None:
            return True
        return False

    def _sync_brain_thumbnail_dna(self, channel: str, dna: ThumbnailDNA) -> None:
        try:
            from app.brain.models import BrainThumbnailDNA
            from app.brain.service import ChannelBrainService

            brains = ChannelBrainService(self._data_root)
            brain = brains.ensure_brain(channel)
            brain.thumbnail_dna = BrainThumbnailDNA.from_learned(dna)
            brains.save(brain)
        except Exception:  # noqa: BLE001
            return

    def _mark_dirty(self, channel: str) -> None:
        marker = self.channel_dir(channel) / ".dna_stale"
        marker.write_text("1\n", encoding="utf-8")

    @staticmethod
    def _next_index(existing: list[Path]) -> int:
        used: set[int] = set()
        for path in existing:
            stem = path.stem  # ref_01
            if "_" in stem:
                try:
                    used.add(int(stem.split("_", 1)[1]))
                except ValueError:
                    continue
        for i in range(1, MAX_REFERENCES + 1):
            if i not in used:
                return i
        return len(existing) + 1
