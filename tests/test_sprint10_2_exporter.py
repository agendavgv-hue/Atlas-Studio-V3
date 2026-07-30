"""Unit tests for ShortsExporter (Sprint 10 component 2)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.shorts.definition import ShortsDefinition
from app.shorts.exporter import ShortsExporter
from app.shorts.naming import SHORTS_FOLDER, short_basename, short_path


class ShortsExporterTests(unittest.TestCase):
    def test_exports_short_01_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition = ShortsDefinition.create(index=1)
            payload = b"\x00\x00fake-mp4-1"
            result = ShortsExporter().export(root, definition, payload)

            expected = short_path(root, 1)
            self.assertEqual(result.path, expected)
            self.assertEqual(result.path.name, short_basename(1))
            self.assertEqual(result.definition_id, definition.definition_id)
            self.assertEqual(result.index, 1)
            self.assertEqual(expected.read_bytes(), payload)
            names = {p.name for p in expected.parent.iterdir() if p.is_file()}
            self.assertEqual(names, {short_basename(1)})
            self.assertEqual(expected.parent.name, SHORTS_FOLDER)

    def test_supports_multiple_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exporter = ShortsExporter()
            exporter.export(root, ShortsDefinition.create(index=1), b"one")
            exporter.export(root, ShortsDefinition.create(index=2), b"two")
            exporter.export(root, ShortsDefinition.create(index=3), b"three")
            self.assertEqual(short_path(root, 1).read_bytes(), b"one")
            self.assertEqual(short_path(root, 2).read_bytes(), b"two")
            self.assertEqual(short_path(root, 3).read_bytes(), b"three")

    def test_export_from_path_copies_without_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "temp_render.mp4"
            source.write_bytes(b"rendered")
            definition = ShortsDefinition.create(index=2)
            result = ShortsExporter().export_from_path(root, definition, source)
            self.assertEqual(result.path.name, "short_02.mp4")
            self.assertEqual(result.path.read_bytes(), b"rendered")
            self.assertTrue(source.is_file())
            self.assertEqual(source.read_bytes(), b"rendered")

    def test_rejects_empty_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                ShortsExporter().export(
                    Path(tmp), ShortsDefinition.create(index=1), b""
                )


if __name__ == "__main__":
    unittest.main()
