"""ShortsExporter — write finished short video files only.

Receives rendered video bytes (or a temp file) and writes ``short/short_NN.mp4``
using the definition index. Does not select, plan, encode, or write manifests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.shorts.definition import ShortsDefinition
from app.shorts.naming import short_basename, short_path


@dataclass(frozen=True)
class ShortsExportResult:
    """Outcome of exporting one short."""

    definition_id: str
    index: int
    path: Path
    bytes_written: int


class ShortsExporter:
    """Project-facing file writer for canonical short MP4s."""

    def export(
        self,
        project_dir: Path,
        definition: ShortsDefinition,
        video_bytes: bytes,
    ) -> ShortsExportResult:
        """Write ``video_bytes`` to ``short/short_{index:02d}.mp4``.

        Raises:
            ValueError: if ``video_bytes`` is empty or index is invalid.
            OSError: if the file cannot be written.
        """
        if not video_bytes:
            raise ValueError("Cannot export an empty short video.")
        if definition.index < 1:
            raise ValueError("Short definition index must be 1-based.")

        path = short_path(project_dir, definition.index)
        # Keep filename consistent with the definition output plan when present.
        expected_name = short_basename(definition.index)
        if definition.output.filename and definition.output.filename != expected_name:
            # Index wins for path stability; definition filename is informational.
            path = path.with_name(expected_name)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(video_bytes)
        return ShortsExportResult(
            definition_id=definition.definition_id,
            index=definition.index,
            path=path,
            bytes_written=len(video_bytes),
        )

    def export_from_path(
        self,
        project_dir: Path,
        definition: ShortsDefinition,
        source_path: Path,
    ) -> ShortsExportResult:
        """Copy a finished temp render into the canonical short path.

        Does not modify ``source_path`` contents beyond reading them.
        """
        if not source_path.is_file():
            raise ValueError(f"Finished short video is missing: {source_path}")
        try:
            payload = source_path.read_bytes()
        except OSError as exc:
            raise ValueError(f"Cannot read finished short video: {exc}") from exc
        return self.export(project_dir, definition, payload)
