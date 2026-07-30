"""Integration tests for Shorts Pipeline / Service (Sprint 10 component 6)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.pipelines.context import ChannelDefaults
from app.pipelines.engine import ProductionEngine
from app.pipelines.results import PipelineOutcome
from app.projects.project_service import ProjectService
from app.shorts.manifest import ShortsManifest
from app.shorts.naming import short_path, shorts_manifest_path
from app.shorts.settings import ShortsSettings
from tests.test_sprint8_movie_pipeline import FakeFFmpeg


def _engine(tmp: Path, ffmpeg: FakeFFmpeg) -> tuple[ProductionEngine, object]:
    data_root = tmp / "atlas"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    Storage(config).ensure_structure()
    projects = ProjectService(config)
    project = projects.create_project(channel, "Atlantis")
    engine = ProductionEngine(projects, config, ffmpeg=ffmpeg)
    context = engine.build_context(
        project,
        channel_defaults=ChannelDefaults(name=channel),
    )
    images = context.folder("images")
    (images / "image_01.png").write_bytes(b"png1")
    (images / "image_02.png").write_bytes(b"png2")
    (images / "image_03.png").write_bytes(b"png3")
    sheet = context.folder("script") / "production_sheet.txt"
    sheet.write_text(
        "IMAGE 01\nDuration: 3\nPrompt: a\n\n"
        "IMAGE 02\nDuration: 4\nPrompt: b\n\n"
        "IMAGE 03\nDuration: 2\nPrompt: c\n",
        encoding="utf-8",
    )
    return engine, context


class ShortsPipelineTests(unittest.TestCase):
    def test_generate_shorts_exports_video_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg()
            engine, context = _engine(Path(tmp), fake)
            stages: list[str] = []
            result = engine.generate_shorts(
                context,
                settings=ShortsSettings(max_shorts=1, motion="none"),
                on_queue_progress=lambda _m, stage: stages.append(stage),
            )
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            final = short_path(context.project_dir, 1)
            self.assertTrue(final.is_file())
            self.assertTrue(shorts_manifest_path(context.project_dir).is_file())
            loaded = ShortsManifest.read_json(shorts_manifest_path(context.project_dir))
            self.assertEqual(loaded.count, 1)
            self.assertEqual(loaded.selection_source, "production_sheet")
            self.assertTrue(loaded.definitions[0].exported)
            self.assertTrue(loaded.definitions[0].definition_id)
            self.assertTrue(any(a.endswith("short_01.mp4") for a in result.artifacts))
            self.assertIn("scenes_selected", stages)
            self.assertIn("planned", stages)
            self.assertIn("finished", stages)

            progress = engine._projects.get_progress(
                context.channel_name,
                context.project_name,
            )
            self.assertTrue(progress.step("shorts").complete)

    def test_regenerate_shorts_aliases_generate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg()
            engine, context = _engine(Path(tmp), fake)
            result = engine.regenerate_shorts(
                context,
                settings=ShortsSettings(max_shorts=1),
            )
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)


if __name__ == "__main__":
    unittest.main()
