"""Design Engine V1 tests."""

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
from app.pipelines.context import PipelineContext
from app.projects.models import Project
from app.providers.image_base import ImageGenerationRequest, ImageGenerationResponse
from app.thumbnail.design_engine.layouts import MIN_LAYOUTS, generate_layouts
from app.thumbnail.design_engine.service import DesignEngineService
from app.thumbnail.design_engine.store import read_design_review
from app.thumbnail.design_engine.typography import invent_line_breaks
from app.thumbnail.design_engine.vision import analyze_illustration
from app.thumbnail.pipeline.brand_composer import BrandComposer
from app.thumbnail.pipeline.engine import ThumbnailPipelineEngine
from app.thumbnail.settings import ThumbnailSettings
from app.thumbnail.style_dna.models import ThumbnailStyleDNA


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _illustration_png() -> bytes:
    _ensure_app()
    image = QImage(320, 180, QImage.Format.Format_ARGB32)
    image.fill(QColor("#15202b"))
    painter = QPainter(image)
    painter.fillRect(180, 20, 120, 140, QColor("#c9a227"))  # subject right
    painter.fillRect(0, 0, 320, 70, QColor("#3a5070"))  # sky
    painter.end()
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
            image_png=_illustration_png(),
            seed=1,
            model="fake",
            width=request.width,
            height=request.height,
            generation_time_ms=1.0,
        )


class DesignEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_app()

    def test_typography_prefers_stacked_dna(self) -> None:
        dna = ThumbnailStyleDNA(
            text_max_lines=3,
            line_break_mode="stacked_words",
            headline_scale=1.8,
        )
        ranked = invent_line_breaks(
            "THE MARY CELESTE", style_dna=dna, max_words=3
        )
        self.assertGreaterEqual(len(ranked), 3)
        best = ranked[0]
        self.assertEqual(best.lines, ["THE", "MARY", "CELESTE"])
        self.assertGreater(best.score, ranked[-1].score)

    def test_vision_and_layout_generation(self) -> None:
        scene = analyze_illustration(_illustration_png())
        self.assertTrue(scene.subject.w > 0)
        self.assertIn(scene.negative_space, {"left", "right"})
        dna = ThumbnailStyleDNA(
            negative_space="left",
            text_position="left",
            logo_position="bottom_left",
            text_max_lines=3,
            line_break_mode="stacked_words",
        )
        breaks = invent_line_breaks("LOST GATE OPEN", style_dna=dna, max_words=3)
        layouts = generate_layouts(scene=scene, style_dna=dna, line_breaks=breaks)
        self.assertGreaterEqual(len(layouts), MIN_LAYOUTS)

    def test_design_service_picks_winner_and_writes_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            studio.ensure("Night Orchard", channel=Channel.create_default("Night Orchard"))
            pack = studio.load_basics("Night Orchard")
            pack.brand.primary_color = "#FFF6D8"
            pack.brand.secondary_color = "#1A1208"
            studio.save(pack)
            brief = CreativeDirectorEngine(root).build_brief("Night Orchard")
            from app.thumbnail.pipeline.plan import ThumbnailCompositionPlanner

            plan = ThumbnailCompositionPlanner().plan(
                brief, hero_subject="gate", hook="LOST GATE"
            )
            assets = BrandComposer(root).resolve_assets(brief, plan)
            project_dir = root / "proj"
            project_dir.mkdir()
            dna = ThumbnailStyleDNA(
                negative_space="left",
                text_position="left",
                logo_position="bottom_left",
                text_max_lines=3,
                line_break_mode="stacked_words",
                headline_scale=1.8,
                text_width=0.38,
                text_top=0.12,
            )
            result = DesignEngineService().design(
                _illustration_png(),
                hook="THE MARY CELESTE",
                assets=assets,
                style_dna=dna,
                channel_name="Night Orchard",
                project_dir=project_dir,
            )
            self.assertGreater(len(result.image_png), 100)
            self.assertGreaterEqual(len(result.board.layouts), MIN_LAYOUTS)
            self.assertTrue(result.winner.id)
            self.assertTrue((project_dir / "thumbnail" / "design_review.json").is_file())
            board = read_design_review(project_dir)
            self.assertIsNotNone(board)
            assert board is not None
            self.assertEqual(board.winner_id, result.winner.id)
            self.assertIn("Winnaar", board.to_dict())

    def test_pipeline_runs_design_engine(self) -> None:
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
                project=project, project_dir=project_dir, data_root=root
            )
            stages: list[str] = []
            result = ThumbnailPipelineEngine(
                ThumbnailSettings(max_quality_attempts=1, primary_variant="A"),
                image_provider=_FakeImageProvider(),
                text_provider=None,
                data_root=root,
                critic_threshold=90,
                on_progress=lambda _m, stage: stages.append(stage),
            ).run(
                ctx,
                script_text="Explorers find an ancient stone gateway vanishing into fog.",
            )
            self.assertTrue(result.ok, result.message)
            self.assertIn("design_engine", stages)
            self.assertIn("design_selected", stages)
            self.assertTrue((project_dir / "thumbnail" / "design_review.json").is_file())
            payload = json.loads(
                (project_dir / "thumbnail" / "design_review.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertGreaterEqual(len(payload.get("layouts") or []), MIN_LAYOUTS)
            self.assertIn("design_review.json", " ".join(result.artifacts))


if __name__ == "__main__":
    unittest.main()
