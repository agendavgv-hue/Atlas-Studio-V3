"""Unit tests for ThumbnailExporter (Sprint 9 component 2)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.thumbnail.exporter import ThumbnailExporter
from app.thumbnail.naming import THUMBNAIL_BASENAME, thumbnail_path


class ThumbnailExporterTests(unittest.TestCase):
    def test_writes_canonical_png_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"\x89PNG\r\n\x1a\nfake"
            result = ThumbnailExporter().export_png(root, payload)

            expected = thumbnail_path(root)
            self.assertEqual(result.path, expected)
            self.assertEqual(result.path.name, THUMBNAIL_BASENAME)
            self.assertEqual(result.bytes_written, len(payload))
            self.assertEqual(expected.read_bytes(), payload)

            # No siblings created by the exporter.
            names = {path.name for path in expected.parent.iterdir() if path.is_file()}
            self.assertEqual(names, {THUMBNAIL_BASENAME})

    def test_overwrites_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = thumbnail_path(root)
            path.write_bytes(b"old")
            ThumbnailExporter().export_png(root, b"new-bytes")
            self.assertEqual(path.read_bytes(), b"new-bytes")

    def test_rejects_empty_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                ThumbnailExporter().export_png(Path(tmp), b"")


if __name__ == "__main__":
    unittest.main()
