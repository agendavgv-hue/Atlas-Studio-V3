"""Reference Library — per-channel creative reference asset folders."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.creative.paths import REFERENCE_KINDS, reference_kind_dir, references_dir


class ReferenceLibrary:
    """Manage reference asset folders (analysis comes later)."""

    def __init__(self, data_root: Path, channel: str) -> None:
        self._data_root = Path(data_root)
        self._channel = channel.strip()

    @property
    def root(self) -> Path:
        return references_dir(self._data_root, self._channel)

    def ensure_structure(self) -> Path:
        root = self.root
        root.mkdir(parents=True, exist_ok=True)
        for kind in REFERENCE_KINDS:
            (root / kind).mkdir(parents=True, exist_ok=True)
        return root

    def list_kinds(self) -> tuple[str, ...]:
        return REFERENCE_KINDS

    def path_for(self, kind: str) -> Path:
        return reference_kind_dir(self._data_root, self._channel, kind)

    def list_files(self, kind: str) -> list[Path]:
        folder = self.path_for(kind)
        if not folder.is_dir():
            return []
        return sorted(
            [p for p in folder.iterdir() if p.is_file()],
            key=lambda p: p.name.casefold(),
        )

    def counts(self) -> dict[str, int]:
        return {kind: len(self.list_files(kind)) for kind in REFERENCE_KINDS}

    def add_file(self, kind: str, source: Path) -> Path:
        src = Path(source)
        if not src.is_file():
            raise FileNotFoundError(f"Reference file not found: {src}")
        dest_dir = self.path_for(kind)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if dest.exists():
            stem, suffix = src.stem, src.suffix
            index = 2
            while dest.exists():
                dest = dest_dir / f"{stem}_{index}{suffix}"
                index += 1
        shutil.copy2(src, dest)
        return dest

    def delete_file(self, kind: str, target: Path) -> None:
        tgt = Path(target).resolve()
        allowed = {p.resolve() for p in self.list_files(kind)}
        if tgt not in allowed:
            raise FileNotFoundError(f"Reference not in library: {target}")
        tgt.unlink(missing_ok=True)
