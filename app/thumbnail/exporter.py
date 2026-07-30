"""ThumbnailExporter — write the final thumbnail file only.

Receives finished image bytes and writes ``thumbnail/thumbnail.png``.
Does not select sources, call providers, mutate pixels, or write manifests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.thumbnail.naming import thumbnail_path


@dataclass(frozen=True)
class ThumbnailExportResult:
    """Outcome of a single PNG export."""

    path: Path
    bytes_written: int


class ThumbnailExporter:
    """Project-facing file writer for the canonical thumbnail PNG."""

    def export_png(self, project_dir: Path, image_png: bytes) -> ThumbnailExportResult:
        """Write ``image_png`` to ``thumbnail/thumbnail.png``.

        Raises:
            ValueError: if ``image_png`` is empty.
            OSError: if the file cannot be written.
        """
        if not image_png:
            raise ValueError("Cannot export an empty thumbnail image.")

        path = thumbnail_path(project_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_png)
        return ThumbnailExportResult(path=path, bytes_written=len(image_png))
