"""Thumbnail Pipeline V3 unit tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.channels.models import Channel
from app.channels.studio.service import ChannelStudioService
from app.creative.engine import CreativeDirectorEngine
from app.creative.engine.style_profile_service import StyleProfileService
from app.pipelines.context import PipelineContext
from app.projects.models import Project
from app.providers.image_base import ImageGenerationRequest, ImageGenerationResponse
from app.thumbnail.pipeline.brand_composer import BrandComposer
from app.thumbnail.pipeline.critic import ThumbnailPipelineCritic
from app.thumbnail.pipeline.debug_report import build_debug_report, write_thumbnail_debug
from app.thumbnail.pipeline.engine import ThumbnailPipelineEngine
from app.thumbnail.pipeline.plan import ThumbnailCompositionPlanner, save_thumbnail_plan
from app.thumbnail.pipeline.prompt_builder import build_pipeline_prompt_plans
from app.thumbnail.pipeline.reference_compare import compare_to_references
from app.thumbnail.naming import thumbnail_debug_path, thumbnail_plan_path
from app.thumbnail.settings import ThumbnailSettings


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _png(path: Path, *, color: str = "#203040") -> None:
    _ensure_app()
    image = QImage(160, 90, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    painter = QPainter(image)
    painter.fillRect(100, 10, 50, 70, QColor("#c9a227"))
    painter.end()
    image.save(str(path), "PNG")


def _png_bytes(*, color: str = "#203040") -> bytes:
    _ensure_app()
    image = QImage(160, 90, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    return bytes(ba)


class _FakeImageProvider:
    provider_id = "fake"

    def validate_ready(self) -> None:
        return None

    def list_models(self) -> list[str]:
        return ["fake"]

    def test_connection(self) -> str:
        return "ok"

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        return ImageGenerationResponse(
            image_png=_png_bytes(color="#182028"),
            seed=1,
            model="fake",
            width=request.width,
            height=request.height,
            generation_time_ms=1.0,
        )


class ThumbnailPipelineV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_app()

    def test_plan_prompt_critic_debug_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            channel = Channel.create_default("Night Orchard")
            channel.description = "Nocturnal nature mystery"
            pack = studio.ensure("Night Orchard", channel=channel)
            pack.brand.primary_color = "#102018"
            pack.brand.secondary_color = "#0a0a0a"
            pack.brand.fonts = ["Impact"]
            pack.thumbnail.emotion = "mystery"
            pack.thumbnail.max_words = 3
            pack.thumbnail.logo_visible = True
            pack.image.lighting = "moonlight"
            pack.story.storytelling_style = "documentary"
            pack.story.mystery = 90
            studio.save(pack)

            logo = root / "logo.png"
            _png(logo, color="#ffffff")
            studio.install_brand_asset("Night Orchard", "thumbnail_logo", logo)
            pack = studio.load_basics("Night Orchard")
            pack.brand.thumbnail_logo = "branding/thumbnail_logo.png"
            studio.save(pack)

            ref = root / "ref.png"
            _png(ref, color="#101820")
            studio.add_reference("Night Orchard", "thumbnails", ref)

            profiles = StyleProfileService(root)
            thumb_profile = profiles.ensure_thumbnail_profile("Night Orchard", force=True)
            engine = CreativeDirectorEngine(root)
            brief = engine.build_brief("Night Orchard")
            brief.project.primary_subject = "ancient stone gateway"
            brief.project.idea = "a lost orchard gate"

            plan = ThumbnailCompositionPlanner().plan(
                brief,
                hero_subject="ancient stone gateway",
                hook="LOST GATE",
                thumbnail_profile=thumb_profile,
            )
            self.assertEqual(plan.main_subject, "ancient stone gateway")
            self.assertIn(plan.negative_space, {"left", "right"})
            self.assertIn(plan.negative_space, plan.text_area)
            plan_file = root / "proj" / "thumbnail" / "thumbnail_plan.json"
            save_thumbnail_plan(plan_file, plan)
            self.assertTrue(plan_file.is_file())

            prompts = build_pipeline_prompt_plans(
                brief, plan, thumbnail_profile=thumb_profile
            )
            self.assertEqual(len(prompts), 4)
            primary = prompts[0].prompt
            self.assertIn("THUMBNAIL PLAN", primary)
            self.assertIn("Night Orchard", primary)
            self.assertIn("Do NOT paint", primary)
            self.assertIn("REFERENCE STYLE", primary)
            self.assertNotIn("Hollow Atlas", primary)

            composed = BrandComposer(root).compose(
                _png_bytes(),
                hook="LOST GATE",
                channel_name="Night Orchard",
                assets=BrandComposer(root).resolve_assets(
                    brief, plan, thumbnail_profile=thumb_profile
                ),
            )
            self.assertGreater(len(composed), 100)

            similarity = compare_to_references(
                composed,
                reference_paths=studio.list_references("Night Orchard", "thumbnails"),
                thumbnail_profile=thumb_profile,
            )
            self.assertGreaterEqual(similarity.reference_count, 1)
            self.assertGreater(similarity.similarity_score, 0)

            critic = ThumbnailPipelineCritic(threshold=90).evaluate(
                brief=brief,
                plan=plan,
                similarity=similarity,
                hook="LOST GATE",
                prompt=primary,
                has_logo=True,
                has_frame=False,
                composed=True,
            )
            self.assertIn("brand_consistency", critic.to_dict())
            self.assertGreater(critic.overall, 50)

            debug = build_debug_report(
                brief=brief,
                plan=plan,
                prompt=primary,
                similarity=similarity,
                critic=critic,
            )
            debug_path = write_thumbnail_debug(root / "proj" / "thumbnail" / "thumbnail_debug.json", debug)
            payload = debug_path.read_text(encoding="utf-8")
            self.assertIn("Thumbnail Plan", payload)
            self.assertIn("Similarity Score", payload)
            self.assertIn("Final Score", payload)

    def test_engine_writes_plan_and_debug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            channel = Channel.create_default("Night Orchard")
            studio.ensure("Night Orchard", channel=channel)
            pack = studio.load_basics("Night Orchard")
            pack.brand.primary_color = "#102018"
            pack.brand.secondary_color = "#050505"
            pack.thumbnail.max_words = 3
            studio.save(pack)
            logo = root / "logo.png"
            _png(logo)
            rel = studio.install_brand_asset("Night Orchard", "logo", logo)
            pack = studio.load_basics("Night Orchard")
            pack.brand.logo = rel
            studio.save(pack)
            ref = root / "ref.png"
            _png(ref)
            studio.add_reference("Night Orchard", "thumbnails", ref)

            project = Project(
                name="Gate",
                folder_name="P001",
                channel_name="Night Orchard",
                idea="ancient stone gateway",
            )
            project_dir = root / "Projects" / "P001"
            project_dir.mkdir(parents=True)
            ctx = PipelineContext(
                project=project,
                project_dir=project_dir,
                data_root=root,
            )
            settings = ThumbnailSettings(max_quality_attempts=1, primary_variant="A")
            stages: list[str] = []
            engine = ThumbnailPipelineEngine(
                settings,
                image_provider=_FakeImageProvider(),
                text_provider=None,
                data_root=root,
                critic_threshold=90,
                on_progress=lambda _m, stage: stages.append(stage),
            )
            result = engine.run(
                ctx,
                script_text=(
                    "In a forgotten valley stands an ancient stone gateway "
                    "covered in moss and moonlight."
                ),
            )
            self.assertTrue(result.ok, result.message)
            self.assertIn("creative_director", stages)
            self.assertIn("creative_director_think", stages)
            self.assertIn("concept_selected", stages)
            self.assertIn("scene_director", stages)
            self.assertIn("scene_selected", stages)
            self.assertTrue(thumbnail_plan_path(project_dir).is_file())
            self.assertTrue(thumbnail_debug_path(project_dir).is_file())
            self.assertTrue((project_dir / "thumbnail" / "thumbnail.png").is_file())
            concepts_path = project_dir / "thumbnail" / "thumbnail_concepts.json"
            self.assertTrue(concepts_path.is_file())
            concepts = json.loads(concepts_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(concepts.get("concepts") or []), 5)
            blueprint_path = project_dir / "thumbnail" / "scene_blueprint.json"
            self.assertTrue(blueprint_path.is_file())
            blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
            self.assertIn("selection_reason", blueprint)
            self.assertGreaterEqual(len(blueprint.get("candidates") or []), 5)
            prompt_text = (project_dir / "thumbnail" / "thumbnail_prompt.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("SCENE BLUEPRINT", prompt_text)
if __name__ == "__main__":
    unittest.main()
