"""Unit tests for ShortsSelector (Sprint 10 component 3)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.shorts.selector import ShortsSelector


class ShortsSelectorTests(unittest.TestCase):
    def _images(self, root: Path, count: int = 3) -> list[Path]:
        folder = root / "images"
        folder.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for index in range(1, count + 1):
            path = folder / f"image_{index:02d}.png"
            path.write_bytes(b"x")
            paths.append(path)
        return paths

    def test_prefers_production_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = self._images(root, 3)
            sheet = """
IMAGE 01
Title: Opening
Duration: 4
Prompt: ruins at dawn

IMAGE 02
Duration: 5.5
Prompt: temple interior

IMAGE 03
Duration: 3
Prompt: map zoom
"""
            selection = ShortsSelector().select(images=images, sheet_text=sheet)
            self.assertEqual(selection.source, "production_sheet")
            self.assertEqual(selection.count, 3)
            self.assertEqual(selection.scenes[0].sheet_ref, "IMAGE 01")
            self.assertEqual(selection.scenes[0].duration_sec, 4.0)
            self.assertEqual(selection.scenes[0].label, "Opening")
            self.assertEqual(selection.scenes[1].duration_sec, 5.5)
            self.assertTrue(selection.scenes[0].image_path.endswith("image_01.png"))
            self.assertEqual(selection.scenes[0].order, 1)

    def test_fallback_when_sheet_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = self._images(root, 2)
            selection = ShortsSelector().select(
                images=images,
                sheet_text="Just a note with no IMAGE blocks.",
            )
            self.assertEqual(selection.source, "images_fallback")
            self.assertEqual(selection.count, 2)
            self.assertIsNone(selection.scenes[0].duration_sec)
            self.assertEqual(Path(selection.scenes[0].image_path).name, "image_01.png")

    def test_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = self._images(root, 3)
            sheet = "IMAGE 01\nPrompt: a\nIMAGE 02\nPrompt: b\nIMAGE 03\nPrompt: c\n"
            a = ShortsSelector().select(images=list(reversed(images)), sheet_text=sheet)
            b = ShortsSelector().select(images=images, sheet_text=sheet)
            self.assertEqual(
                [(s.image_path, s.sheet_index, s.duration_sec) for s in a.scenes],
                [(s.image_path, s.sheet_index, s.duration_sec) for s in b.scenes],
            )

    def test_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = self._images(root, 1)
            ShortsSelector().select(images=images, sheet_text=None)
            self.assertFalse((root / "short").exists())


if __name__ == "__main__":
    unittest.main()
