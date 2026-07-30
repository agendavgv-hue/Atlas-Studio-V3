"""Unit tests for ShortsPlanner (Sprint 10 component 4)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.shorts.planner import ShortsPlanner
from app.shorts.selection import SceneSelection, SelectedScene
from app.shorts.settings import ShortsSettings


def _selection(*paths: str, source: str = "production_sheet") -> SceneSelection:
    scenes = tuple(
        SelectedScene(
            order=i,
            image_path=path,
            sheet_index=i,
            sheet_ref=f"IMAGE {i:02d}",
            duration_sec=float(2 + i),
            label=f"Scene {i}",
        )
        for i, path in enumerate(paths, start=1)
    )
    return SceneSelection(scenes=scenes, source=source, rationale="test")


class ShortsPlannerTests(unittest.TestCase):
    def test_defaults_to_single_definition_list(self) -> None:
        selection = _selection("images/image_01.png", "images/image_02.png")
        definitions = ShortsPlanner().plan(selection)
        self.assertIsInstance(definitions, list)
        self.assertEqual(len(definitions), 1)
        self.assertEqual(definitions[0].index, 1)
        self.assertEqual(len(definitions[0].scenes), 2)
        self.assertEqual(definitions[0].output.filename, "short_01.mp4")
        self.assertEqual(definitions[0].timing_source, "production_sheet")
        self.assertFalse(definitions[0].intro.enabled)
        self.assertFalse(definitions[0].outro.enabled)
        self.assertFalse(definitions[0].hook.enabled)
        self.assertFalse(definitions[0].cta.enabled)

    def test_always_returns_list_even_for_one(self) -> None:
        definitions = ShortsPlanner().plan(
            _selection("images/image_01.png"),
        )
        self.assertEqual(type(definitions), list)
        self.assertEqual(len(definitions), 1)

    def test_deterministic_ids_and_content(self) -> None:
        selection = _selection("a.png", "b.png")
        settings = ShortsSettings(max_shorts=1, motion="none")
        first = ShortsPlanner(settings).plan(selection)
        second = ShortsPlanner(settings).plan(selection)
        self.assertEqual(first[0].definition_id, second[0].definition_id)
        self.assertEqual(first[0].total_duration_sec, second[0].total_duration_sec)
        self.assertEqual(
            [s.image_path for s in first[0].scenes],
            [s.image_path for s in second[0].scenes],
        )

    def test_multi_short_setting_splits_deterministically(self) -> None:
        selection = _selection("a.png", "b.png", "c.png", "d.png")
        definitions = ShortsPlanner(ShortsSettings(max_shorts=2)).plan(selection)
        self.assertEqual(len(definitions), 2)
        self.assertEqual(definitions[0].index, 1)
        self.assertEqual(definitions[1].index, 2)
        self.assertEqual(definitions[0].output.filename, "short_01.mp4")
        self.assertEqual(definitions[1].output.filename, "short_02.mp4")
        self.assertNotEqual(definitions[0].definition_id, definitions[1].definition_id)

    def test_voice_plan_when_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            voice = Path(tmp) / "voice.mp3"
            voice.write_bytes(b"ID3")
            definitions = ShortsPlanner().plan(
                _selection("a.png"),
                voice_path=voice,
                voice_duration_sec=9.0,
            )
            self.assertTrue(definitions[0].voice.use_voice)
            self.assertEqual(definitions[0].voice.voice_path, str(voice))

    def test_empty_selection_returns_empty_list(self) -> None:
        empty = SceneSelection(scenes=(), source="images_fallback", rationale="")
        self.assertEqual(ShortsPlanner().plan(empty), [])


if __name__ == "__main__":
    unittest.main()
