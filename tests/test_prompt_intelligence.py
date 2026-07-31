"""Tests for Prompt Intelligence Engine (no new AI steps)."""

from __future__ import annotations

import unittest

from app.thumbnail.anti_ai import AntiAiRulesLoader
from app.thumbnail.composition import CompositionPlanner
from app.thumbnail.dna_loader import ChannelDNALoader
from app.thumbnail.prompt_builder import ThumbnailPromptBuilder
from app.thumbnail.prompt_intelligence import (
    ASSEMBLY_ORDER,
    PromptBlocks,
    PromptIntelligenceEngine,
    ModelProfileLoader,
)
from app.thumbnail.prompt_intelligence.optimizer import optimize_text
from app.thumbnail.prompt_intelligence.semantics import resolve_contradictions
from app.thumbnail.style_loader import ChannelStyleLoader
from app.thumbnail.thumbnail_director import ThumbnailStrategy


class PromptIntelligenceUnitTests(unittest.TestCase):
    def test_model_profiles_resolve_aliases(self) -> None:
        loader = ModelProfileLoader()
        flux = loader.get_profile("flux-dev")
        self.assertEqual(flux.display_name, "Flux Dev")
        self.assertFalse(flux.use_commas)
        sdxl = loader.get_profile("SDXL")
        self.assertTrue(sdxl.prefer_short_blocks)
        self.assertTrue(sdxl.use_commas)
        jug = loader.get_profile("juggernaut")
        self.assertTrue(jug.cinematography_bias)
        default = loader.get_profile("")
        self.assertEqual(default.key, "default")

    def test_optimizer_strips_buzzwords_and_filler(self) -> None:
        text = optimize_text(
            "stunning masterpiece beautiful Baghdad Battery ultra detailed 8k"
        )
        lowered = text.casefold()
        self.assertIn("baghdad", lowered)
        self.assertNotIn("masterpiece", lowered)
        self.assertNotIn("stunning", lowered)
        self.assertNotIn("8k", lowered)

    def test_semantics_rewrites_contradictions(self) -> None:
        blocks = PromptBlocks(
            subject="Baghdad Battery close-up",
            camera="tight crop close-up",
            environment="wide landscape panorama behind the hero",
            lighting="moonlit night",
            mood="bright midday energy",
        )
        report = resolve_contradictions(blocks)
        joined = " ".join(
            [
                report.blocks.subject,
                report.blocks.camera,
                report.blocks.environment,
                report.blocks.lighting,
                report.blocks.mood,
            ]
        ).casefold()
        self.assertIn("close-up", joined)
        self.assertNotIn("wide landscape", joined)
        self.assertNotIn("panorama", joined)
        self.assertTrue(report.fixed)

    def test_assembly_follows_visual_priority_and_model_separator(self) -> None:
        strategy = ThumbnailStrategy(
            emotion="Mystery",
            click_reason="Impossible ancient technology.",
            hero_subject="Baghdad Battery",
            dominant_feeling="curiosity",
        )
        style = ChannelStyleLoader().get_style("Hollow Atlas")
        dna = ChannelDNALoader().get_dna("Hollow Atlas")
        composition = CompositionPlanner().plan(strategy=strategy, style=style)
        anti = AntiAiRulesLoader().load()
        engine = PromptIntelligenceEngine()

        flux = engine.build(
            strategy=strategy,
            hero_subject="Baghdad Battery",
            composition=composition,
            style=style,
            dna=dna,
            anti_ai=anti,
            variant_mood="restrained mystery",
            model_name="Flux Dev",
        )
        sdxl = engine.build(
            strategy=strategy,
            hero_subject="Baghdad Battery",
            composition=composition,
            style=style,
            dna=dna,
            anti_ai=anti,
            variant_mood="restrained mystery",
            model_name="SDXL",
        )
        self.assertIn("Baghdad Battery", flux.prompt)
        self.assertTrue(flux.prompt.index("Baghdad") < flux.prompt.casefold().find("warm gold") or "warm gold" in flux.prompt.casefold())
        # Subject block should appear before environment cues in assembly order.
        subject_pos = flux.prompt.casefold().find("single hero")
        env_pos = flux.prompt.casefold().find("supporting background")
        self.assertGreaterEqual(subject_pos, 0)
        self.assertGreaterEqual(env_pos, 0)
        self.assertLess(subject_pos, env_pos)
        self.assertNotEqual(flux.profile.key, sdxl.profile.key)
        self.assertGreaterEqual(flux.quality.total, 50)
        self.assertEqual(ASSEMBLY_ORDER[0], "subject")
        self.assertEqual(ASSEMBLY_ORDER[1], "lighting")

    def test_prompt_builder_writes_block_metadata(self) -> None:
        strategy = ThumbnailStrategy(
            emotion="Mystery",
            click_reason="Impossible ancient technology.",
            hero_subject="Baghdad Battery",
            dominant_feeling="curiosity",
        )
        style = ChannelStyleLoader().get_style("Hollow Atlas")
        dna = ChannelDNALoader().get_dna("Hollow Atlas")
        composition = CompositionPlanner().plan(strategy=strategy, style=style)
        anti = AntiAiRulesLoader().load()
        plans = ThumbnailPromptBuilder(model_name="Juggernaut XL").build_variants(
            strategy=strategy,
            hero_subject="Baghdad Battery",
            composition=composition,
            style=style,
            dna=dna,
            anti_ai=anti,
            model_name="Juggernaut XL",
        )
        self.assertEqual(len(plans), 4)
        self.assertTrue(plans[0].blocks)
        self.assertIn("subject", plans[0].blocks or {})
        self.assertTrue(plans[0].prompt_quality)
        self.assertIn("cinematic", plans[0].prompt.casefold())


if __name__ == "__main__":
    unittest.main()
