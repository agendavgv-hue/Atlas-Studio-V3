"""Unit tests for Shorts naming / definition / manifest (Sprint 10 component 1)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.shorts.definition import ShortsDefinition, ShortsScene, new_definition_id
from app.shorts.manifest import ShortsManifest
from app.shorts.naming import (
    MANIFEST_BASENAME,
    SHORTS_FOLDER,
    short_basename,
    short_path,
    shorts_manifest_path,
)


class ShortsNamingTests(unittest.TestCase):
    def test_short_basename_and_paths(self) -> None:
        self.assertEqual(short_basename(1), "short_01.mp4")
        self.assertEqual(short_basename(12), "short_12.mp4")
        with self.assertRaises(ValueError):
            short_basename(0)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = short_path(root, 1)
            self.assertEqual(path.parent.name, SHORTS_FOLDER)
            self.assertEqual(path.name, "short_01.mp4")
            self.assertEqual(shorts_manifest_path(root).name, MANIFEST_BASENAME)


class ShortsDefinitionTests(unittest.TestCase):
    def test_create_assigns_stable_unique_id(self) -> None:
        first = ShortsDefinition.create(index=1, scenes=[])
        second = ShortsDefinition.create(index=2, scenes=[])
        self.assertTrue(first.definition_id)
        self.assertTrue(second.definition_id)
        self.assertNotEqual(first.definition_id, second.definition_id)
        self.assertEqual(first.index, 1)

    def test_round_trip_preserves_definition_id(self) -> None:
        fixed = new_definition_id()
        definition = ShortsDefinition.create(
            index=1,
            definition_id=fixed,
            scenes=[
                ShortsScene(
                    index=1,
                    image_path="images/image_01.png",
                    duration_sec=3.0,
                    motion="zoom_in",
                )
            ],
            timing_source="production_sheet",
            total_duration_sec=3.0,
            rationale="Sheet scene 1",
        )
        loaded = ShortsDefinition.from_dict(definition.to_dict())
        self.assertEqual(loaded.definition_id, fixed)
        self.assertEqual(loaded.scenes[0].image_path, "images/image_01.png")
        self.assertEqual(loaded.intro.kind, "intro")
        self.assertFalse(loaded.intro.enabled)
        self.assertEqual(loaded.hook.kind, "hook")
        self.assertEqual(loaded.cta.kind, "cta")
        self.assertEqual(loaded.output.profile, "shorts")
        self.assertEqual(loaded.output.width, 1080)
        self.assertEqual(loaded.output.height, 1920)


class ShortsManifestTests(unittest.TestCase):
    def test_manifest_holds_multiple_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definitions = [
                ShortsDefinition.create(index=1, title="A"),
                ShortsDefinition.create(index=2, title="B"),
            ]
            manifest = ShortsManifest.from_definitions(
                definitions,
                selection_source="production_sheet",
                rationale="Two planned shorts",
            )
            self.assertEqual(manifest.count, 2)
            path = shorts_manifest_path(root)
            manifest.write_json(path)
            loaded = ShortsManifest.read_json(path)
            self.assertEqual(loaded.count, 2)
            self.assertEqual(loaded.selection_source, "production_sheet")
            ids = {item.definition_id for item in loaded.definitions}
            self.assertEqual(len(ids), 2)
            found = loaded.definition_by_id(definitions[0].definition_id)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.title, "A")


if __name__ == "__main__":
    unittest.main()
