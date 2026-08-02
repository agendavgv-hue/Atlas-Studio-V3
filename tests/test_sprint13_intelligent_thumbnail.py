"""Integration tests for Intelligent Thumbnail Engine (Phase 2 + 3)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.pipelines.context import ChannelDefaults
from app.pipelines.engine import ProductionEngine
from app.pipelines.results import PipelineOutcome
from app.projects.project_service import ProjectService
from app.providers.base import TextProvider
from app.providers.image_base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)
from app.thumbnail.anti_ai import AntiAiRulesLoader
from app.thumbnail.composition import CompositionPlanner, HERO_SHARE, NEGATIVE_SPACE_SHARE
from app.thumbnail.critic import PrimaryVariantCritic, ThumbnailCandidate
from app.thumbnail.dna_loader import ChannelDNALoader
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.naming import (
    THUMBNAIL_CONCEPTS_BASENAME,
    THUMBNAIL_DEBUG_BASENAME,
    THUMBNAIL_PLAN_BASENAME,
    THUMBNAIL_PROMPT_BASENAME,
    THUMBNAIL_TITLE_BASENAME,
    thumbnail_debug_path,
    thumbnail_path,
    thumbnail_plan_path,
    thumbnail_prompt_path,
    thumbnail_title_path,
    thumbnail_variant_path,
)
from app.thumbnail.settings import ThumbnailSettings
from app.thumbnail.style_loader import ChannelStyleLoader
from app.thumbnail.thumbnail_director import ThumbnailStrategy


class _FakeImageProvider(ImageProvider):
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.negatives: list[str] = []

    @property
    def provider_id(self) -> str:
        return "fake"

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self.prompts.append(request.prompt)
        self.negatives.append(request.negative_prompt)
        from PySide6.QtCore import QByteArray, QBuffer, QIODevice
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication
        import sys

        if QApplication.instance() is None:
            QApplication(sys.argv[:1])
        image = QImage(320, 180, QImage.Format.Format_ARGB32)
        image.fill(QColor("#1a2030"))
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buf, "PNG")
        buf.close()
        return ImageGenerationResponse(
            image_png=bytes(ba),
            seed=1,
            model="fake",
            width=request.width or 1280,
            height=request.height or 720,
        )

    def list_models(self) -> list[str]:
        return ["fake"]

    def test_connection(self) -> str:
        return "ok"

    def validate_ready(self) -> None:
        return None


class _FakeTextProvider(TextProvider):
    """Director → analyzer → critique (×4)."""

    def __init__(self, *, fail_critique: bool = False) -> None:
        self.calls = 0
        self.fail_critique = fail_critique

    @property
    def provider_id(self) -> str:
        return "fake-text"

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        del system
        self.calls += 1
        lowered = (prompt or "").casefold()
        if "distinct possible thumbnail scenes" in lowered or "scene director" in lowered:
            return json.dumps(
                {
                    "scenes": [
                        {
                            "id": 1,
                            "title": "IMPOSSIBLE CHARGE",
                            "story": (
                                "An explorer realizes the Baghdad Battery still sparks "
                                "while torchlight ruins collapse behind them in fog."
                            ),
                            "emotion": "mystery",
                            "main_subject": "explorer silhouette",
                            "secondary_subject": "Baghdad Battery",
                            "background": "collapsing torchlit ruins",
                            "foreground": "ancient clay vessel glowing",
                            "lighting": "warm rim light",
                            "weather": "dust haze",
                            "camera": "eye_level",
                            "lens": "35mm cinematic",
                            "depth": "layered ruins depth",
                            "atmosphere": "documentary mystery",
                            "negative_space": "left",
                            "color_palette": ["#c9a227", "#1a2030"],
                            "visual_focus": "explorer reacting to battery spark",
                        },
                        {
                            "id": 2,
                            "title": "NOT NATURAL",
                            "story": (
                                "A researcher measures the Baghdad Battery beside geometry "
                                "that should not exist as a desert storm builds."
                            ),
                            "emotion": "curiosity",
                            "main_subject": "researcher",
                            "secondary_subject": "Baghdad Battery",
                            "background": "impossible stone chamber",
                            "foreground": "measurement tools",
                            "lighting": "documentary key light",
                            "weather": "approaching storm",
                            "negative_space": "left",
                        },
                        {
                            "id": 3,
                            "title": "TOO LATE",
                            "story": (
                                "A rescue craft turns away as the Baghdad Battery flares "
                                "and the sea around the excavation collapses inward."
                            ),
                            "emotion": "fear",
                            "main_subject": "small rescue craft",
                            "secondary_subject": "Baghdad Battery",
                            "background": "collapsing coastal dig site",
                            "foreground": "spray and rope",
                            "lighting": "urgent red-gold light",
                            "weather": "chaotic spray",
                            "negative_space": "left",
                        },
                        {
                            "id": 4,
                            "title": "JUST REVEALED",
                            "story": (
                                "From a cliff edge an explorer looks down as a hidden "
                                "workshop emerges through mist while the Baghdad Battery glows."
                            ),
                            "emotion": "wonder",
                            "main_subject": "explorer",
                            "secondary_subject": "Baghdad Battery",
                            "background": "hidden workshop through mist",
                            "foreground": "cliff edge stones",
                            "lighting": "pale dawn",
                            "weather": "thick mist",
                            "negative_space": "left",
                        },
                        {
                            "id": 5,
                            "title": "THE VANISHING",
                            "story": (
                                "An explorer stands alone as footprints end mid-chamber "
                                "and the Baghdad Battery still spins with unnatural light."
                            ),
                            "emotion": "mystery",
                            "main_subject": "explorer",
                            "secondary_subject": "Baghdad Battery",
                            "background": "abandoned dig chamber",
                            "foreground": "ending footprints",
                            "lighting": "cold blue moonlight",
                            "weather": "rolling fog",
                            "negative_space": "left",
                        },
                    ]
                }
            )
        if "invent exactly 3 thumbnail concepts" in lowered or "invent exactly 5 thumbnail concepts" in lowered or "chosen_concept_id" in lowered or "invent at least" in lowered:
            return json.dumps(
                {
                    "selected_scene": "Baghdad Battery discovered in ruins",
                    "click_value_reason": "Impossible ancient power",
                    "concepts": [
                        {
                            "id": 1,
                            "title": "WHO BUILT THIS?",
                            "foreground": "Baghdad Battery close-up",
                            "midground": "ruins",
                            "background": "dark chamber",
                            "lighting": "warm rim light",
                            "emotion": "mystery",
                            "elements": ["battery", "ruins", "dust"],
                            "hero_subject": "Baghdad Battery",
                            "hook": "WHO BUILT THIS?",
                            "idea": "Baghdad Battery close-up in dark ruins",
                        },
                        {
                            "id": 2,
                            "title": "NOT HUMAN?",
                            "foreground": "Hands holding the jar",
                            "midground": "artifact",
                            "background": "torchlight cave",
                            "lighting": "torch glow",
                            "emotion": "curiosity",
                            "elements": ["hands", "jar"],
                            "hero_subject": "Baghdad Battery",
                            "hook": "NOT HUMAN?",
                            "idea": "Hands holding the jar artifact",
                        },
                        {
                            "id": 3,
                            "title": "SECRET POWER",
                            "foreground": "Sparks inside clay vessel",
                            "midground": "vessel",
                            "background": "workshop",
                            "lighting": "electric glow",
                            "emotion": "wonder",
                            "elements": ["sparks", "vessel"],
                            "hero_subject": "Baghdad Battery",
                            "hook": "SECRET POWER",
                            "idea": "Sparks inside clay vessel",
                        },
                        {
                            "id": 4,
                            "title": "ANCIENT TECH",
                            "foreground": "cutaway battery diagram feel",
                            "midground": "tools",
                            "background": "excavation site",
                            "lighting": "documentary daylight",
                            "emotion": "discovery",
                            "elements": ["battery", "tools", "site"],
                            "hero_subject": "Baghdad Battery",
                            "hook": "ANCIENT TECH",
                            "idea": "Documentary evidence layout",
                        },
                        {
                            "id": 5,
                            "title": "LOST CHARGE",
                            "foreground": "cracked vessel silhouette",
                            "midground": "sand",
                            "background": "desert dusk",
                            "lighting": "golden dusk",
                            "emotion": "mystery",
                            "elements": ["vessel", "sand", "dusk"],
                            "hero_subject": "Baghdad Battery",
                            "hook": "LOST CHARGE",
                            "idea": "Cracked vessel at dusk",
                        },
                    ],
                    "chosen_concept_id": 1,
                    "chosen_reason": "Strong mystery CTR",
                    "hero_subject": "Baghdad Battery",
                    "emotion": "Mystery",
                    "click_reason": "An impossible ancient technology that should not exist.",
                    "dominant_feeling": "unsettling curiosity",
                }
            )
        if "do not write an image prompt" in lowered or '"emotion": one of' in lowered:
            return json.dumps(
                {
                    "emotion": "Mystery",
                    "click_reason": "An impossible ancient technology that should not exist.",
                    "hero_subject": "Baghdad Battery",
                    "dominant_feeling": "unsettling curiosity",
                    "rationale": "Mystery drives the click harder than dry history.",
                }
            )
        if "critique this thumbnail" in lowered or "rewritten_prompt" in lowered:
            if self.fail_critique:
                return json.dumps(
                    {
                        "passed": False,
                        "checks": {
                            "single_hero": True,
                            "simple_composition": False,
                            "supporting_background": True,
                            "readable_small": True,
                            "empty_headline_side": False,
                            "channel_recognizable": True,
                        },
                        "notes": "Too busy; left side crowded.",
                        "rewritten_prompt": (
                            "Professional YouTube thumbnail, single hero Baghdad Battery, "
                            "clean composition, empty left headline space, Hollow Atlas DNA, "
                            "Mystery emotion, no clutter."
                        ),
                    }
                )
            return json.dumps(
                {
                    "passed": True,
                    "checks": {
                        "single_hero": True,
                        "simple_composition": True,
                        "supporting_background": True,
                        "readable_small": True,
                        "empty_headline_side": True,
                        "channel_recognizable": True,
                    },
                    "notes": "Passes Channel DNA.",
                    "rewritten_prompt": "",
                }
            )
        return json.dumps(
            {
                "hero_subject": "Baghdad Battery",
                "hook": "WHO BUILT THIS?",
                "rationale": "The battery is the one unforgettable icon.",
            }
        )


def _engine(
    tmp: Path,
    *,
    text: _FakeTextProvider | None = None,
) -> tuple[ProductionEngine, object, _FakeImageProvider, _FakeTextProvider]:
    data_root = tmp / "atlas"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    Storage(config).ensure_structure()
    projects = ProjectService(config)
    project = projects.create_project(channel, "Baghdad Battery")
    images = _FakeImageProvider()
    text_provider = text or _FakeTextProvider()
    engine = ProductionEngine(
        projects,
        config,
        image_provider=images,
        text_provider=text_provider,
    )
    context = engine.build_context(
        project,
        channel_defaults=ChannelDefaults(name=channel),
    )
    script_dir = context.folder("script")
    (script_dir / "script.txt").write_text(
        "The Baghdad Battery may have generated ancient electric power.",
        encoding="utf-8",
    )
    images_dir = context.folder("images")
    (images_dir / "image_01.png").write_bytes(b"png1")
    (images_dir / "image_02.png").write_bytes(b"png2")
    (images_dir / "image_03.png").write_bytes(b"png3")
    return engine, context, images, text_provider


class IntelligentThumbnailTests(unittest.TestCase):
    def test_intelligent_exports_strategy_dna_memory_and_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, context, images, text = _engine(Path(tmp))
            stages: list[str] = []
            result = engine.generate_thumbnail(
                context,
                on_queue_progress=lambda _m, stage: stages.append(stage),
            )
            self.assertTrue(result.ok, result.message)
            self.assertGreaterEqual(text.calls, 1)

            plan_path = thumbnail_plan_path(context.project_dir)
            self.assertTrue(plan_path.is_file())
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertTrue(plan.get("main_subject"))
            self.assertTrue(plan.get("secondary_subject") or plan.get("story_focus"))
            self.assertIn("Baghdad Battery", json.dumps(plan))

            blueprint_path = context.project_dir / "thumbnail" / "scene_blueprint.json"
            self.assertTrue(blueprint_path.is_file())
            blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
            self.assertIn("selection_reason", blueprint)
            self.assertGreaterEqual(len(blueprint.get("candidates") or []), 5)

            prompt_path = thumbnail_prompt_path(context.project_dir)
            self.assertTrue(prompt_path.is_file())
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn("Baghdad Battery", prompt_text)
            self.assertIn("SCENE BLUEPRINT", prompt_text)
            self.assertIn("THUMBNAIL PLAN", prompt_text)
            self.assertIn("Do NOT paint", prompt_text)

            debug_path = thumbnail_debug_path(context.project_dir)
            self.assertTrue(debug_path.is_file())
            debug = json.loads(debug_path.read_text(encoding="utf-8"))
            self.assertIn("Final Score", debug)
            self.assertIn("Similarity Score", debug)

            self.assertTrue(thumbnail_path(context.project_dir).is_file())
            title = thumbnail_title_path(context.project_dir)
            self.assertEqual(title.read_text(encoding="utf-8").strip(), "WHO BUILT THIS?")

            for variant_id in ("A", "B", "C", "D"):
                self.assertTrue(
                    thumbnail_variant_path(context.project_dir, variant_id).is_file()
                )
            self.assertGreaterEqual(len(images.prompts), 4)
            self.assertTrue(any("Baghdad Battery" in p for p in images.prompts))
            self.assertTrue(any("text" in n.casefold() for n in images.negatives))
            # One attempt = 4 variants; retries may add more when critic < 90.
            self.assertEqual(len(images.prompts) % 4, 0)

            self.assertIn("creative_director", stages)
            self.assertIn("concept_selected", stages)
            self.assertIn("scene_director", stages)
            self.assertIn("scene_selected", stages)
            self.assertIn("planner", stages)
            self.assertIn("design_engine", stages)
            self.assertIn("design_selected", stages)
            self.assertIn("critic", stages)
            self.assertIn(THUMBNAIL_CONCEPTS_BASENAME, " ".join(result.artifacts))
            self.assertIn("scene_blueprint.json", " ".join(result.artifacts))
            self.assertIn(THUMBNAIL_PLAN_BASENAME, " ".join(result.artifacts))
            self.assertIn(THUMBNAIL_DEBUG_BASENAME, " ".join(result.artifacts))
            self.assertIn(THUMBNAIL_PROMPT_BASENAME, " ".join(result.artifacts))
            self.assertIn(THUMBNAIL_TITLE_BASENAME, " ".join(result.artifacts))
            concepts = json.loads(
                (context.project_dir / "thumbnail" / THUMBNAIL_CONCEPTS_BASENAME).read_text(
                    encoding="utf-8"
                )
            )
            self.assertGreaterEqual(len(concepts.get("concepts") or []), 5)
            self.assertIn("selected_reason", concepts)

    def test_critique_rewrites_failing_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, context, images, _text = _engine(
                Path(tmp), text=_FakeTextProvider(fail_critique=True)
            )
            result = engine.generate_thumbnail(context)
            self.assertTrue(result.ok, result.message)
            # Pipeline V3 embeds plan + no-text rules in every prompt.
            self.assertTrue(any("THUMBNAIL PLAN" in p for p in images.prompts))
            self.assertTrue(any("Do NOT paint" in p for p in images.prompts))
            debug = json.loads(
                thumbnail_debug_path(context.project_dir).read_text(encoding="utf-8")
            )
            self.assertIn("critic", debug)
            self.assertGreaterEqual(float(debug.get("Final Score") or 0), 0)

    def test_select_mode_still_copies_middle_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, context, _images, _text = _engine(Path(tmp))
            result = engine.generate_thumbnail(
                context,
                settings=ThumbnailSettings(mode=ThumbnailMode.SELECT.value),
            )
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(thumbnail_path(context.project_dir).read_bytes(), b"png2")

    def test_channel_dna_and_style_loaders(self) -> None:
        dna = ChannelDNALoader().get_dna("Hollow Atlas")
        self.assertIn("gold", dna.color_language.primary.casefold())
        self.assertEqual(dna.visual_language.hero_subjects, 1)
        self.assertEqual(dna.visual_language.headline_side, "left")
        self.assertTrue(dna.signature)
        self.assertIn("Hollow Atlas", dna.dna_block())

        style = ChannelStyleLoader().get_style("Hollow Atlas")
        self.assertTrue(style.lighting)
        mirror = ChannelDNALoader().get_dna("Mirror Drift")
        self.assertIn("blue", mirror.color_language.secondary.casefold())

        anti = AntiAiRulesLoader().load()
        self.assertTrue(anti.forbidden)
        merged = anti.merge_negative("custom ban")
        self.assertIn("custom ban", merged)
        self.assertIn("busy composition", merged.casefold())

    def test_composition_planner_uses_channel_style_not_hardcoded_channel(self) -> None:
        style = ChannelStyleLoader().get_style("Hollow Atlas")
        strategy = ThumbnailStrategy(
            emotion="Curiosity",
            click_reason="Something impossible was found.",
            hero_subject="Baghdad Battery",
            dominant_feeling="need to know",
        )
        plan = CompositionPlanner().plan(strategy=strategy, style=style)
        self.assertEqual(plan.light_source, style.lighting)
        self.assertEqual(plan.camera_angle, style.camera)
        self.assertEqual(plan.background, style.background_style)
        self.assertIn(str(int(HERO_SHARE * 100)), plan.prompt_block())
        self.assertIn(str(int(NEGATIVE_SPACE_SHARE * 100)), plan.prompt_block())
        self.assertIn("Curiosity", strategy.emotion)
        self.assertTrue(plan.emotion_accent)

    def test_primary_variant_critic_is_swappable_hook(self) -> None:
        candidates = [
            ThumbnailCandidate("A", "mystery", b"a"),
            ThumbnailCandidate("B", "epic", b"b"),
        ]
        result = PrimaryVariantCritic("B").select(candidates)
        self.assertEqual(result.winner_variant_id, "B")
        self.assertTrue(result.deferred)
        self.assertEqual(result.selection_method, "settings_primary")


if __name__ == "__main__":
    unittest.main()
