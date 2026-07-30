"""Unit tests for ThumbnailSelector (Sprint 9 component 3)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.selector import SelectionDecision, ThumbnailSelector
from app.thumbnail.settings import ThumbnailSettings


class _PickFirstScorer:
    def pick(self, images: list[Path], *, prompt: str = "") -> Path | None:
        return images[0] if images else None


class ThumbnailSelectorTests(unittest.TestCase):
    def _images(self, root: Path, count: int = 3) -> list[Path]:
        folder = root / "images"
        folder.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for index in range(1, count + 1):
            path = folder / f"image_{index:02d}.png"
            path.write_bytes(b"x")
            paths.append(path)
        return paths

    def test_select_mode_picks_middle_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = self._images(root, 3)
            decision = ThumbnailSelector(
                ThumbnailSettings(mode=ThumbnailMode.SELECT.value)
            ).select(images=images)
            self.assertIsInstance(decision, SelectionDecision)
            self.assertEqual(decision.mode, ThumbnailMode.SELECT)
            self.assertEqual(decision.source_image_path, images[1])
            self.assertIn("image_02", decision.rationale)
            self.assertEqual(decision.prompt, "")

    def test_generate_mode_uses_prompt_without_source(self) -> None:
        decision = ThumbnailSelector(
            ThumbnailSettings(mode=ThumbnailMode.GENERATE.value, width=1280, height=720)
        ).select(
            images=[],
            thumbnail_prompt="bold youtube thumbnail",
            negative_prompt="blurry",
        )
        self.assertEqual(decision.mode, ThumbnailMode.GENERATE)
        self.assertIsNone(decision.source_image_path)
        self.assertEqual(decision.prompt, "bold youtube thumbnail")
        self.assertEqual(decision.negative_prompt, "blurry")
        self.assertEqual(decision.generation.width, 1280)
        self.assertEqual(decision.generation.height, 720)

    def test_candidates_mode_uses_heuristic_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = self._images(root, 5)
            before = {path.name: path.read_bytes() for path in images}
            decision = ThumbnailSelector(
                ThumbnailSettings(mode=ThumbnailMode.CANDIDATES.value)
            ).select(images=images)
            self.assertEqual(decision.mode, ThumbnailMode.CANDIDATES)
            self.assertEqual(decision.source_image_path, images[2])
            for path in images:
                self.assertEqual(path.read_bytes(), before[path.name])
            self.assertFalse((root / "thumbnail").exists())

    def test_ai_scored_uses_injected_scorer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = self._images(root, 3)
            decision = ThumbnailSelector(
                ThumbnailSettings(mode=ThumbnailMode.AI_SCORED.value),
                scorer=_PickFirstScorer(),
            ).select(images=images)
            self.assertEqual(decision.mode, ThumbnailMode.AI_SCORED)
            self.assertEqual(decision.source_image_path, images[0])
            self.assertIn("AI-scored", decision.rationale)

    def test_decision_is_immutable(self) -> None:
        decision = ThumbnailSelector().select(images=[])
        with self.assertRaises(Exception):
            decision.prompt = "mutated"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
