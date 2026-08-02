"""Thumbnail Critic & Improve Engine tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from app.channels.models import Channel
from app.channels.studio.service import ChannelStudioService
from app.creative.engine import CreativeDirectorEngine
from app.pipelines.context import PipelineContext
from app.projects.models import Project
from app.providers.image_base import ImageGenerationRequest, ImageGenerationResponse
from app.thumbnail.critic_engine import (
    CRITIC_AXES,
    ImproveEngine,
    ThumbnailCriticService,
    read_review_board,
)
from app.thumbnail.critic_engine.learning import CriticLearningStore
from app.thumbnail.pipeline.engine import ThumbnailPipelineEngine
from app.thumbnail.pipeline.plan import ThumbnailCompositionPlanner
from app.thumbnail.pipeline.reference_compare import ReferenceSimilarityReport
from app.thumbnail.settings import ThumbnailSettings
from app.thumbnail.style_dna.models import ThumbnailStyleDNA


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _png_bytes() -> bytes:
    _ensure_app()
    image = QImage(160, 90, QImage.Format.Format_ARGB32)
    image.fill(QColor("#182028"))
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
            image_png=_png_bytes(),
            seed=1,
            model="fake",
            width=request.width,
            height=request.height,
            generation_time_ms=1.0,
        )


class CriticEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_app()

    def test_critic_scores_all_axes_and_improve_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            studio.ensure("Night Orchard", channel=Channel.create_default("Night Orchard"))
            brief = CreativeDirectorEngine(root).build_brief("Night Orchard")
            brief.project.primary_subject = "compass"
            plan = ThumbnailCompositionPlanner().plan(
                brief, hero_subject="explorer", hook="LOST SHIP"
            )
            similarity = ReferenceSimilarityReport(
                reference_count=1,
                similarity_score=62.0,
                composition=70.0,
                lighting=65.0,
                contrast=68.0,
                atmosphere=70.0,
            )
            dna = ThumbnailStyleDNA(
                text_position="left",
                text_max_lines=3,
                headline_scale=1.8,
                logo_position="bottom_left",
                logo_scale=0.11,
                subject_position="right",
                negative_space="left",
                reference_count=2,
            )
            report = ThumbnailCriticService(threshold=90).evaluate(
                brief=brief,
                plan=plan,
                similarity=similarity,
                hook="LOST SHIP",
                prompt="a lonely compass on a table",
                has_logo=False,
                has_frame=False,
                composed=True,
                style_dna=dna,
            )
            self.assertEqual(len(report.axes), len(CRITIC_AXES))
            self.assertIn("story", report.groups.to_dict())
            self.assertFalse(report.approved)
            weak = report.weak_axes()
            self.assertTrue(weak)
            for axis in report.axes:
                self.assertTrue(axis.why)
                self.assertTrue(axis.improvement)

            improve = ImproveEngine().build_plan(report, style_dna=dna)
            self.assertTrue(improve.summary_lines)
            self.assertIn("IMPROVE PLAN", improve.prompt_block())
            # Only weak axes
            for action in improve.actions:
                self.assertLess(report.axis_map()[action.axis].score, 90)

    def test_learning_records_high_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            studio.ensure("Night Orchard", channel=Channel.create_default("Night Orchard"))
            brief = CreativeDirectorEngine(root).build_brief("Night Orchard")
            plan = ThumbnailCompositionPlanner().plan(
                brief, hero_subject="explorer", hook="SECRET GATE"
            )
            similarity = ReferenceSimilarityReport(
                reference_count=2,
                similarity_score=92.0,
                composition=90.0,
                lighting=91.0,
                contrast=90.0,
                atmosphere=88.0,
            )
            report = ThumbnailCriticService(threshold=50).evaluate(
                brief=brief,
                plan=plan,
                similarity=similarity,
                hook="SECRET GATE",
                prompt="explorer discovers glowing gate in fog",
                has_logo=True,
                has_frame=True,
                composed=True,
                style_dna=ThumbnailStyleDNA(reference_count=2, logo_position="bottom_left"),
            )
            # Force high overall for learning path
            report.overall = 92.0
            for axis in report.axes:
                axis.score = max(axis.score, 90.0)
            memory = CriticLearningStore(root).record_win("Night Orchard", report)
            self.assertGreaterEqual(memory.wins, 1)
            self.assertTrue(memory.strong_traits)
            self.assertTrue(memory.prompt_hints())

    def test_pipeline_writes_review_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            studio.ensure("Night Orchard", channel=Channel.create_default("Night Orchard"))
            pack = studio.load_basics("Night Orchard")
            pack.brand.primary_color = "#102018"
            pack.thumbnail.max_words = 3
            studio.save(pack)

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
            stages: list[str] = []
            engine = ThumbnailPipelineEngine(
                ThumbnailSettings(max_quality_attempts=2, primary_variant="A"),
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
                    "covered in moss while explorers vanish into fog."
                ),
            )
            self.assertTrue(result.ok, result.message)
            self.assertIn("critic", stages)
            board = read_review_board(project_dir)
            self.assertIsNotNone(board)
            assert board is not None
            self.assertGreaterEqual(len(board.versions), 1)
            self.assertTrue((project_dir / "thumbnail" / "thumbnail_review.json").is_file())
            payload = json.loads(
                (project_dir / "thumbnail" / "thumbnail_review.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("Winnaar", payload)
            self.assertIn("versions", payload)
            self.assertIn("thumbnail_review.json", " ".join(result.artifacts))


if __name__ == "__main__":
    unittest.main()
