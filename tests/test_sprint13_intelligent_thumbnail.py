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
from app.thumbnail.manifest import ThumbnailManifest
from app.thumbnail.memory import ThumbnailMemoryRecord
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.naming import (
    THUMBNAIL_MEMORY_BASENAME,
    THUMBNAIL_PROMPT_BASENAME,
    THUMBNAIL_PROMPT_QUALITY_BASENAME,
    THUMBNAIL_QUALITY_BASENAME,
    THUMBNAIL_STRATEGY_BASENAME,
    THUMBNAIL_TITLE_BASENAME,
    thumbnail_critique_path,
    thumbnail_history_path,
    thumbnail_manifest_path,
    thumbnail_memory_path,
    thumbnail_path,
    thumbnail_prompt_path,
    thumbnail_prompt_quality_path,
    thumbnail_quality_path,
    thumbnail_strategy_path,
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
        return ImageGenerationResponse(
            image_png=f"PNG:{request.prompt[:24]}".encode("utf-8"),
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
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS, result.message)
            self.assertGreaterEqual(text.calls, 6)  # director + analyzer + 4 critiques

            strategy_path = thumbnail_strategy_path(context.project_dir)
            self.assertTrue(strategy_path.is_file())
            strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
            self.assertEqual(strategy["emotion"], "Mystery")

            prompt_path = thumbnail_prompt_path(context.project_dir)
            self.assertTrue(prompt_path.is_file())
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn("Mystery", prompt_text)
            self.assertIn("Baghdad Battery", prompt_text)
            self.assertIn("warm gold", prompt_text.casefold())
            self.assertIn("single hero", prompt_text.casefold())
            self.assertTrue(thumbnail_prompt_quality_path(context.project_dir).is_file())
            prompt_quality = json.loads(
                thumbnail_prompt_quality_path(context.project_dir).read_text(encoding="utf-8")
            )
            self.assertIn("total", prompt_quality)
            self.assertIn("coherence", prompt_quality)
            self.assertGreaterEqual(prompt_quality["total"], 50)

            self.assertTrue(thumbnail_critique_path(context.project_dir).is_file())
            self.assertTrue(thumbnail_quality_path(context.project_dir).is_file())
            quality = json.loads(
                thumbnail_quality_path(context.project_dir).read_text(encoding="utf-8")
            )
            self.assertTrue(quality["approved"])
            self.assertGreaterEqual(quality["score"], 80)
            history = json.loads(
                thumbnail_history_path(context.project_dir).read_text(encoding="utf-8")
            )
            self.assertGreaterEqual(len(history.get("entries") or []), 1)
            memory_path = thumbnail_memory_path(context.project_dir)
            self.assertTrue(memory_path.is_file())
            memory = ThumbnailMemoryRecord.read_json(memory_path)
            self.assertEqual(memory.hero_subject, "Baghdad Battery")
            self.assertEqual(memory.emotion, "Mystery")
            self.assertEqual(memory.hook, "WHO BUILT THIS?")
            self.assertTrue(memory.channel_dna)
            self.assertEqual(memory.channel_dna.get("channel_key"), "Hollow Atlas")
            self.assertTrue(memory.composition)
            self.assertEqual(len(memory.variants), 4)
            self.assertTrue(memory.critic_ready)
            self.assertEqual(memory.selection_method, "settings_primary")

            self.assertTrue(thumbnail_path(context.project_dir).is_file())
            title = thumbnail_title_path(context.project_dir)
            self.assertEqual(title.read_text(encoding="utf-8").strip(), "WHO BUILT THIS?")

            for variant_id in ("A", "B", "C", "D"):
                self.assertTrue(
                    thumbnail_variant_path(context.project_dir, variant_id).is_file()
                )
            self.assertEqual(len(images.prompts), 4)
            self.assertTrue(any("Baghdad Battery" in p for p in images.prompts))
            self.assertTrue(any("single hero" in p.casefold() for p in images.prompts))
            self.assertTrue(
                any("busy composition" in n.casefold() for n in images.negatives)
            )

            loaded = ThumbnailManifest.read_json(
                thumbnail_manifest_path(context.project_dir)
            )
            self.assertEqual(loaded.extras.get("emotion"), "Mystery")
            self.assertEqual(loaded.extras.get("channel_dna"), "Hollow Atlas")
            self.assertTrue(loaded.extras.get("critic_ready"))
            self.assertIn("dna", stages)
            self.assertIn("critique", stages)
            self.assertIn("qa", stages)
            self.assertIn("qa_approved", stages)
            self.assertIn("critic", stages)
            self.assertIn("memory", stages)
            self.assertIn(THUMBNAIL_MEMORY_BASENAME, " ".join(result.artifacts))
            self.assertIn(THUMBNAIL_QUALITY_BASENAME, " ".join(result.artifacts))
            self.assertIn(THUMBNAIL_PROMPT_QUALITY_BASENAME, " ".join(result.artifacts))
            self.assertIn(THUMBNAIL_STRATEGY_BASENAME, " ".join(result.artifacts))
            self.assertIn(THUMBNAIL_PROMPT_BASENAME, " ".join(result.artifacts))
            self.assertIn(THUMBNAIL_TITLE_BASENAME, " ".join(result.artifacts))

    def test_critique_rewrites_failing_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, context, images, _text = _engine(
                Path(tmp), text=_FakeTextProvider(fail_critique=True)
            )
            result = engine.generate_thumbnail(context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS, result.message)
            self.assertTrue(
                any("STRICT DNA" in p or "empty left" in p.casefold() for p in images.prompts)
            )
            critique = json.loads(
                thumbnail_critique_path(context.project_dir).read_text(encoding="utf-8")
            )
            self.assertTrue(any(item.get("rewritten") for item in critique["variants"]))

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
