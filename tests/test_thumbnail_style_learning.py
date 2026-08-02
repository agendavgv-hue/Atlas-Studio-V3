"""Thumbnail Style learning — references, DNA, concept planner integration."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.channels.channel_ids import channel_id
from app.models.thumbnail_dna import ThumbnailDNA
from app.services.thumbnail_dna_service import ThumbnailDNAService
from app.services.thumbnail_reference_service import ThumbnailReferenceService
from app.thumbnail.composition import CompositionPlanner
from app.thumbnail.concept_planner import ThumbnailConceptPlanner
from app.thumbnail.style_loader import ChannelThumbnailStyle
from app.thumbnail.thumbnail_director import ThumbnailStrategy


def _png(path: Path) -> Path:
    # Minimal 1x1 PNG
    path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
    )
    return path


class ChannelIdTests(unittest.TestCase):
    def test_slugifies_any_channel(self) -> None:
        self.assertEqual(channel_id("Hollow Atlas"), "hollow_atlas")
        self.assertEqual(channel_id("WonderNest Stories"), "wondernest_stories")
        self.assertEqual(channel_id("Mirror Drift"), "mirror_drift")


class ReferenceServiceTests(unittest.TestCase):
    def test_save_load_delete_and_analyze_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = ThumbnailReferenceService(root, text_provider=None)
            channel = "Night Orchard"
            a = _png(root / "a.png")
            b = _png(root / "b.png")

            p1 = service.save_reference(channel, a)
            p2 = service.save_reference(channel, b)
            self.assertTrue(p1.is_file())
            self.assertEqual(service.reference_count(channel), 2)
            self.assertTrue(service.is_dna_stale(channel))

            refs = service.load_references(channel)
            self.assertEqual(len(refs), 2)

            dna = service.analyze(channel)
            self.assertIsInstance(dna, ThumbnailDNA)
            self.assertEqual(dna.reference_count, 2)
            self.assertEqual(dna.channel_id, "night_orchard")
            self.assertFalse(service.is_dna_stale(channel))

            loaded = service.get_thumbnail_dna(channel)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.style.emotion, "mystery")

            path = ThumbnailDNAService(root).dna_path(channel)
            self.assertTrue(path.is_file())
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("layout", raw)
            self.assertIn("colors", raw)

            service.delete_reference(channel, p2)
            self.assertEqual(service.reference_count(channel), 1)
            self.assertTrue(service.is_dna_stale(channel))

    def test_max_ten_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = ThumbnailReferenceService(root)
            channel = "Test Channel"
            for i in range(10):
                service.save_reference(channel, _png(root / f"r{i}.png"))
            with self.assertRaises(ValueError):
                service.save_reference(channel, _png(root / "overflow.png"))


class ConceptPlannerTests(unittest.TestCase):
    def test_parses_concepts_and_choice(self) -> None:
        provider = MagicMock()
        provider.generate_text.return_value = json.dumps(
            {
                "selected_scene": "empty deck in fog",
                "click_value_reason": "void creates curiosity",
                "concepts": [
                    {"id": 1, "title": "Ship in fog", "idea": "hull vanishing"},
                    {"id": 2, "title": "Captain disappears", "idea": "empty coat"},
                    {"id": 3, "title": "Empty deck", "idea": "footprints end"},
                ],
                "chosen_concept_id": 3,
                "chosen_reason": "strongest void",
                "emotion": "Mystery",
                "hero_subject": "empty wooden deck fading into fog",
                "click_reason": "Where did everyone go?",
                "dominant_feeling": "unease",
            }
        )
        plan = ThumbnailConceptPlanner(provider).plan(
            script_text="A ship sails into fog and the crew vanishes.",
            channel_name="Demo",
            thumbnail_dna=ThumbnailDNA(channel_name="Demo"),
        )
        self.assertEqual(plan.chosen.title, "Empty deck")
        self.assertEqual(plan.strategy.hero_subject, "empty wooden deck fading into fog")
        self.assertEqual(len(plan.concepts), 5)  # pads to minimum 5


class CompositionWithDnaTests(unittest.TestCase):
    def test_thumbnail_dna_overrides_layout(self) -> None:
        style = ChannelThumbnailStyle(
            channel_key="x",
            display_name="x",
            colors="c",
            lighting="studio",
            style="s",
            atmosphere="a",
            composition="hero right",
            camera="medium",
            contrast="high",
            texture="t",
            background_style="bg",
            headline_position="left",
            headline_color="white",
            headline_shadow="dark",
            hero_scale="40%",
            depth="deep",
            negative_prompt="n",
            thumbnail_rules="r",
        )
        dna = ThumbnailDNA.from_dict(
            {
                "layout": {
                    "title_position": "top",
                    "subject_position": "center",
                    "negative_space": "top",
                },
                "style": {"lighting": "mist", "contrast": "very_high", "emotion": "wonder"},
                "composition": {
                    "subject_scale": "large",
                    "focus": "face",
                    "gaze_direction": "camera",
                },
            }
        )
        plan = CompositionPlanner().plan(
            strategy=ThumbnailStrategy(
                emotion="Wonder",
                click_reason="why",
                hero_subject="hero",
            ),
            style=style,
            thumbnail_dna=dna,
        )
        self.assertIn("center", plan.hero_position)
        self.assertEqual(plan.headline_position, "top")
        self.assertEqual(plan.light_source, "mist")


if __name__ == "__main__":
    unittest.main()
