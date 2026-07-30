"""Integration tests for Thumbnail Pipeline / Service (Sprint 9 component 5)."""

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
from app.providers.image_base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)
from app.thumbnail.manifest import ThumbnailManifest
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.naming import thumbnail_manifest_path, thumbnail_path
from app.thumbnail.settings import ThumbnailSettings


class _FakeImageProvider(ImageProvider):
    @property
    def provider_id(self) -> str:
        return "fake"

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        return ImageGenerationResponse(
            image_png=b"\x89PNG-generated-thumb",
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


def _engine(tmp: Path, *, provider: ImageProvider | None = None) -> tuple[ProductionEngine, object]:
    data_root = tmp / "atlas"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    Storage(config).ensure_structure()
    projects = ProjectService(config)
    project = projects.create_project(channel, "Atlantis")
    engine = ProductionEngine(
        projects,
        config,
        image_provider=provider or _FakeImageProvider(),
    )
    context = engine.build_context(
        project,
        channel_defaults=ChannelDefaults(
            name=channel,
            thumbnail_prompt="epic clickable thumbnail",
            negative_prompt="blurry",
        ),
    )
    images = context.folder("images")
    (images / "image_01.png").write_bytes(b"png1")
    (images / "image_02.png").write_bytes(b"png2")
    (images / "image_03.png").write_bytes(b"png3")
    return engine, context


class ThumbnailPipelineTests(unittest.TestCase):
    def test_select_mode_exports_png_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, context = _engine(Path(tmp))
            stages: list[str] = []
            result = engine.generate_thumbnail(
                context,
                settings=ThumbnailSettings(mode=ThumbnailMode.SELECT.value),
                on_queue_progress=lambda _m, stage: stages.append(stage),
            )
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            final = thumbnail_path(context.project_dir)
            self.assertTrue(final.is_file())
            self.assertEqual(final.read_bytes(), b"png2")  # middle image
            manifest_file = thumbnail_manifest_path(context.project_dir)
            self.assertTrue(manifest_file.is_file())
            loaded = ThumbnailManifest.read_json(manifest_file)
            self.assertEqual(loaded.mode, ThumbnailMode.SELECT.value)
            self.assertTrue(loaded.exported)
            self.assertTrue(
                any(a.endswith("thumbnail.png") for a in result.artifacts)
            )
            self.assertIn("selected", stages)
            self.assertIn("exported", stages)
            self.assertIn("finished", stages)

            progress = engine._projects.get_progress(
                context.channel_name,
                context.project_name,
            )
            self.assertTrue(progress.step("thumbnail").complete)

    def test_generate_mode_uses_provider_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, context = _engine(Path(tmp))
            result = engine.generate_thumbnail(
                context,
                settings=ThumbnailSettings(mode=ThumbnailMode.GENERATE.value),
            )
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(
                thumbnail_path(context.project_dir).read_bytes(),
                b"\x89PNG-generated-thumb",
            )
            loaded = ThumbnailManifest.read_json(
                thumbnail_manifest_path(context.project_dir)
            )
            self.assertEqual(loaded.mode, ThumbnailMode.GENERATE.value)
            assert loaded.generation is not None
            self.assertEqual(loaded.generation.prompt, "epic clickable thumbnail")
            self.assertEqual(loaded.generation.provider_id, "fake")

    def test_regenerate_thumbnail_aliases_generate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, context = _engine(Path(tmp))
            result = engine.regenerate_thumbnail(
                context,
                settings=ThumbnailSettings(mode=ThumbnailMode.SELECT.value),
            )
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)


if __name__ == "__main__":
    unittest.main()
