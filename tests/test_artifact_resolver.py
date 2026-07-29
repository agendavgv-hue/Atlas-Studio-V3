"""Artifact Resolver — purpose-based file lookup."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.artifacts import ArtifactKind, ArtifactResolver


class ArtifactResolverTests(unittest.TestCase):
    def test_finds_script_by_purpose_not_exact_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_dir = root / "script"
            script_dir.mkdir()
            (script_dir / "my_screenplay.md").write_text("hello", encoding="utf-8")
            (script_dir / "notes.txt").write_text("ignore prefer screenplay", encoding="utf-8")

            resolver = ArtifactResolver(root)
            found = resolver.find(ArtifactKind.SCRIPT)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.name, "my_screenplay.md")

    def test_finds_renamed_production_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_dir = root / "script"
            script_dir.mkdir()
            (script_dir / "episode_story.txt").write_text("script", encoding="utf-8")
            (script_dir / "scene_breakdown.txt").write_text("sheet", encoding="utf-8")

            resolver = ArtifactResolver(root)
            self.assertEqual(resolver.find(ArtifactKind.SCRIPT).name, "episode_story.txt")  # type: ignore[union-attr]
            self.assertEqual(
                resolver.find(ArtifactKind.PRODUCTION_SHEET).name,
                "scene_breakdown.txt",
            )

    def test_script_excludes_production_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_dir = root / "script"
            script_dir.mkdir()
            (script_dir / "production_sheet.txt").write_text("sheet only", encoding="utf-8")

            resolver = ArtifactResolver(root)
            self.assertIsNone(resolver.find(ArtifactKind.SCRIPT))
            self.assertTrue(resolver.exists(ArtifactKind.PRODUCTION_SHEET))

    def test_images_and_youtube_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            (root / "images" / "frame_01.png").write_bytes(b"x")
            (root / "youtube_video").mkdir()
            (root / "youtube_video" / "final.mp4").write_bytes(b"x")

            resolver = ArtifactResolver(root)
            self.assertTrue(resolver.exists(ArtifactKind.IMAGES))
            self.assertEqual(resolver.find(ArtifactKind.YOUTUBE_EXPORT).name, "final.mp4")  # type: ignore[union-attr]

    def test_thumbnail_hint_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "thumbnail"
            folder.mkdir()
            (folder / "cover.png").write_bytes(b"a")
            (folder / "video_thumb.jpg").write_bytes(b"b")

            found = ArtifactResolver(root).find(ArtifactKind.THUMBNAIL)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.name, "video_thumb.jpg")


if __name__ == "__main__":
    unittest.main()
