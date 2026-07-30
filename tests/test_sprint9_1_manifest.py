"""Unit tests for Thumbnail Manifest (Sprint 9 component 1)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.thumbnail.manifest import ManifestGeneration, ThumbnailManifest
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.naming import (
    MANIFEST_BASENAME,
    THUMBNAIL_BASENAME,
    thumbnail_manifest_path,
    thumbnail_path,
)


class ThumbnailNamingTests(unittest.TestCase):
    def test_paths_use_standard_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(thumbnail_path(root).name, THUMBNAIL_BASENAME)
            self.assertEqual(thumbnail_manifest_path(root).name, MANIFEST_BASENAME)
            self.assertEqual(thumbnail_path(root).parent.name, "thumbnail")
            self.assertTrue(thumbnail_path(root).parent.is_dir())


class ThumbnailManifestTests(unittest.TestCase):
    def test_select_mode_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = ThumbnailManifest(
                mode=ThumbnailMode.SELECT.value,
                source_image_path=str(root / "images" / "image_02.png"),
                rationale="Middle scene image",
                exported=True,
            )
            path = thumbnail_manifest_path(root)
            manifest.write_json(path)
            loaded = ThumbnailManifest.read_json(path)
            self.assertEqual(loaded.mode, ThumbnailMode.SELECT.value)
            self.assertEqual(loaded.output.filename, THUMBNAIL_BASENAME)
            self.assertTrue(loaded.exported)
            self.assertEqual(loaded.source_image_path, str(root / "images" / "image_02.png"))
            self.assertIsNone(loaded.generation)
            self.assertIsNone(loaded.ai_score)

    def test_generate_mode_records_provider_request_snapshot(self) -> None:
        manifest = ThumbnailManifest(
            mode=ThumbnailMode.GENERATE.value,
            rationale="Channel thumbnail prompt",
            generation=ManifestGeneration(
                provider_id="forge",
                prompt="epic thumbnail, high contrast",
                negative_prompt="blurry",
                width=1280,
                height=720,
                seed=42,
                model="demo",
            ),
            exported=False,
        )
        loaded = ThumbnailManifest.from_dict(manifest.to_dict())
        self.assertEqual(loaded.mode, ThumbnailMode.GENERATE.value)
        assert loaded.generation is not None
        self.assertEqual(loaded.generation.provider_id, "forge")
        self.assertEqual(loaded.generation.prompt, "epic thumbnail, high contrast")
        self.assertEqual(loaded.generation.seed, 42)
        self.assertEqual(loaded.branding.logo_path, None)
        self.assertEqual(loaded.text.title, "")


if __name__ == "__main__":
    unittest.main()
