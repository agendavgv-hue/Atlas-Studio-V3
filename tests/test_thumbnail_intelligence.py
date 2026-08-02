"""Thumbnail Intelligence 1.0 tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
import json

from app.channels.models import Channel
from app.creative import CreativeDirectorService
from app.models.thumbnail_dna import ThumbnailDNA
from app.thumbnail.intelligence.branding import ThumbnailBrandingService
from app.thumbnail.intelligence.consistency import score_thumbnail_consistency
from app.thumbnail.intelligence.context import load_intelligence_context
from app.thumbnail.intelligence.prompt_builder import ThumbnailIntelligencePromptBuilder
from app.thumbnail.intelligence.settings import ThumbnailStudioSettings, ThumbnailStudioSettingsStore
from app.thumbnail.intelligence.planner import ThumbnailPlanner
from app.thumbnail.concept_planner import ConceptPlan, ThumbnailConcept
from app.thumbnail.thumbnail_director import ThumbnailStrategy


class BrandingAutoPositionTests(unittest.TestCase):
    def test_auto_position_rules(self) -> None:
        branding = ThumbnailBrandingService()
        self.assertEqual(branding.auto_position("right"), "bottom_left")
        self.assertEqual(branding.auto_position("left"), "bottom_right")
        self.assertEqual(branding.auto_position("center"), "bottom_left")

        settings = ThumbnailStudioSettings(logo_visible=True, logo_position="auto")
        dna = ThumbnailDNA.from_dict({"layout": {"subject_position": "left"}})
        placement = branding.resolve_logo_placement(
            settings=settings, dna=dna, subject_position="left"
        )
        assert placement is not None
        self.assertEqual(placement.position, "bottom_right")


class StudioSettingsTests(unittest.TestCase):
    def test_save_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ThumbnailStudioSettingsStore(Path(tmp))
            settings = ThumbnailStudioSettings(
                style_strength=88,
                brand_strength=91,
                max_words=3,
                logo_position="top_right",
            )
            store.save("Night Orchard", settings)
            loaded = store.load("Night Orchard")
            self.assertEqual(loaded.style_strength, 88)
            self.assertEqual(loaded.max_words, 3)
            self.assertEqual(loaded.logo_position, "top_right")


class IntelligenceContextTests(unittest.TestCase):
    def test_loads_director_brand_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            channel = Channel.create_default("Night Orchard")
            channel.image_prompt = "moonlit orchard"
            CreativeDirectorService(root).create("Night Orchard", source=channel)
            brand = CreativeDirectorService(root).get_brand("Night Orchard")
            brand.primary_color = "#c9a227"
            CreativeDirectorService(root).save_brand("Night Orchard", brand)

            ctx = load_intelligence_context(root, "Night Orchard")
            self.assertIsNotNone(ctx.director)
            self.assertEqual(ctx.brand.primary_color, "#c9a227")
            brief = ctx.identity_brief()
            self.assertIn("director", brief.casefold())


class PromptBuilderTests(unittest.TestCase):
    def test_builds_without_hardcoded_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            CreativeDirectorService(root).create("Demo Channel")
            intelligence = load_intelligence_context(root, "Demo Channel")
            strategy = ThumbnailStrategy(
                emotion="Mystery",
                click_reason="why click",
                hero_subject="foggy gate",
            )
            concept_plan = ConceptPlan(
                selected_scene="gate",
                click_value_reason="curiosity",
                concepts=(
                    ThumbnailConcept(1, "Close-up", "face"),
                    ThumbnailConcept(2, "Object", "key"),
                    ThumbnailConcept(3, "Wide", "landscape"),
                ),
                chosen=ThumbnailConcept(1, "Close-up", "face in fog"),
                chosen_reason="ctr",
                strategy=strategy,
            )
            from app.thumbnail.intelligence.planner import ThumbnailPlan

            plan = ThumbnailPlan(
                concept_plan=concept_plan,
                intelligence_brief=intelligence.identity_brief(),
                selected_scene="gate",
                chosen_title="Close-up",
            )
            built = ThumbnailIntelligencePromptBuilder().build(
                plan=plan,
                intelligence=intelligence,
                hero_subject="foggy gate",
                hook="WHO BUILT THIS?",
            )
            self.assertIn("foggy gate", built.prompt.casefold())
            self.assertIn("do not paint text", built.prompt.casefold())
            consistency = score_thumbnail_consistency(
                intelligence, prompt=built.prompt, hook="WHO BUILT THIS?"
            )
            self.assertGreaterEqual(consistency.overall, 70)
            payload = intelligence.to_critic_payload(hook="WHO BUILT THIS?", prompt=built.prompt)
            self.assertIn("hook", payload)


class DnaExtensibilityTests(unittest.TestCase):
    def test_future_fields_roundtrip(self) -> None:
        dna = ThumbnailDNA.from_dict(
            {
                "layout": {"title_position": "left"},
                "typography": {"max_words": 3, "weight": "black"},
                "safe_areas": {"margin_px": 64},
                "future_metric": 42,
            }
        )
        raw = dna.to_dict()
        self.assertEqual(dna.typography.max_words, 3)
        self.assertEqual(dna.safe_areas.margin_px, 64)
        self.assertEqual(raw["extras"].get("future_metric"), 42)
        again = ThumbnailDNA.from_dict(raw)
        self.assertEqual(again.extras.get("future_metric"), 42)


if __name__ == "__main__":
    unittest.main()
