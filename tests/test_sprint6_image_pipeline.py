"""Sprint 6 — Image Pipeline tests (fake Forge only)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.pipelines.context import ChannelDefaults
from app.pipelines.engine import ProductionEngine
from app.pipelines.image_naming import image_basename, resolve_images_dir
from app.pipelines.results import PipelineOutcome
from app.pipelines.sheet_prompts import extract_image_prompts
from app.projects.project_service import ProjectService
from app.providers.errors import ProviderError
from app.providers.image_base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)


class FakeImageProvider(ImageProvider):
    """Test-only provider."""

    def __init__(
        self,
        *,
        fail_indexes: set[int] | None = None,
        ready_error: str | None = None,
    ) -> None:
        self.calls: list[ImageGenerationRequest] = []
        self._fail = fail_indexes or set()
        self._ready_error = ready_error
        self._n = 0

    @property
    def provider_id(self) -> str:
        return "fake-image"

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self._n += 1
        self.calls.append(request)
        if self._n in self._fail:
            raise ProviderError(f"simulated failure #{self._n}")
        return ImageGenerationResponse(
            image_png=b"\x89PNG\r\n\x1a\n" + f"img{self._n}".encode(),
            seed=42 + self._n,
            model="fake-model",
            sampler="DPM++ 2M Karras",
            steps=30,
            cfg_scale=7.0,
            width=1024,
            height=1024,
            generation_time_ms=12.5,
        )

    def list_models(self) -> list[str]:
        return ["fake-model"]

    def test_connection(self) -> str:
        if self._ready_error:
            raise ProviderError(self._ready_error)
        return "Fake OK"

    def validate_ready(self) -> None:
        if self._ready_error:
            raise ProviderError(self._ready_error)


_SHEET_V3 = """
IMAGE 01
Prompt:
A ruined temple under moonlight

IMAGE 02
Prompt:
Aerial view of an ancient harbor

Image Prompt: Close-up of a bronze statue
"""

_SHEET_V2 = """
Scene 1
Image Prompt: Desert caravan at dusk

Scene 2
Image Prompt: Oasis pool reflecting stars
"""


def _engine(tmp: Path, provider: ImageProvider) -> tuple[ProductionEngine, object]:
    data_root = tmp / "atlas"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    config.image_provider = "forge"
    Storage(config).ensure_structure()
    projects = ProjectService(config)
    project = projects.create_project(channel, "Atlantis")
    engine = ProductionEngine(projects, config, image_provider=provider)
    context = engine.build_context(
        project,
        channel_defaults=ChannelDefaults(name=channel, image_prompt="cinematic"),
    )
    sheet = context.folder("script") / "production_sheet.txt"
    sheet.write_text(_SHEET_V3, encoding="utf-8")
    return engine, context


class SheetPromptExtractionTests(unittest.TestCase):
    def test_extracts_image_nn_and_image_prompt(self) -> None:
        prompts = extract_image_prompts(_SHEET_V3)
        self.assertEqual(len(prompts), 3)
        self.assertIn("ruined temple", prompts[0].prompt)
        self.assertIn("bronze statue", prompts[2].prompt)

    def test_extracts_v2_image_prompt_lines(self) -> None:
        prompts = extract_image_prompts(_SHEET_V2)
        self.assertEqual(len(prompts), 2)
        self.assertIn("Desert caravan", prompts[0].prompt)


class ImagePipelineTests(unittest.TestCase):
    def test_generate_all_writes_images_metadata_and_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeImageProvider()
            engine, context = _engine(Path(tmp), fake)
            seen: list[tuple[int, int, str]] = []

            result = engine.generate_images(
                context,
                on_queue_progress=lambda c, t, m, p="": seen.append((c, t, m, p)),
            )

            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(result.queue_total, 3)
            self.assertEqual(result.succeeded_indexes, [1, 2, 3])
            self.assertEqual(result.failed_indexes, [])
            self.assertEqual(len(seen), 3)
            self.assertEqual(seen[0][2], "Image 1 / 3")
            self.assertIn("ruined temple", seen[0][3].casefold())

            for index in (1, 2, 3):
                png = context.folder("images") / image_basename(index)
                meta = png.with_suffix(".json")
                self.assertTrue(png.is_file())
                self.assertFalse(meta.is_file())

            progress = engine.last_progress
            self.assertIsNotNone(progress)
            assert progress is not None
            self.assertTrue(progress.step("images").complete)

    def test_partial_failure_continues_and_reports_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeImageProvider(fail_indexes={2})
            engine, context = _engine(Path(tmp), fake)
            result = engine.generate_images(context)
            self.assertEqual(result.outcome, PipelineOutcome.WARNING)
            self.assertEqual(result.failed_indexes, [2])
            self.assertEqual(result.succeeded_indexes, [1, 3])
            self.assertTrue((context.folder("images") / "image_01.png").is_file())
            self.assertFalse((context.folder("images") / "image_02.png").is_file())
            self.assertTrue((context.folder("images") / "image_03.png").is_file())

    def test_generate_single_image_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeImageProvider()
            engine, context = _engine(Path(tmp), fake)
            result = engine.generate_image(context, 2)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(result.succeeded_indexes, [2])
            self.assertTrue((context.folder("images") / "image_02.png").is_file())
            self.assertFalse((context.folder("images") / "image_01.png").is_file())

    def test_missing_image_provider_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "atlas"
            project_root = Path(tmp) / "youtube"
            channel = "Hollow Atlas"
            (project_root / channel).mkdir(parents=True)
            config = AppConfig(data_root=data_root, project_root=project_root)
            config.image_provider = ""
            Storage(config).ensure_structure()
            projects = ProjectService(config)
            project = projects.create_project(channel, "No Provider")
            engine = ProductionEngine(projects, config)
            context = engine.build_context(project)
            (context.folder("script") / "production_sheet.txt").write_text(
                "Image Prompt: test\n", encoding="utf-8"
            )
            # Empty host forces configuration error when provider unset.
            config.forge.host = ""
            result = engine.generate_images(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)

    def test_cancel_stops_before_next_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeImageProvider()
            engine, context = _engine(Path(tmp), fake)

            class _CancellingProvider(FakeImageProvider):
                def generate_image(self, request):
                    result = super().generate_image(request)
                    engine.request_cancel()
                    return result

            engine._image_provider_override = _CancellingProvider()
            result = engine.generate_images(context)
            self.assertEqual(result.outcome, PipelineOutcome.CANCELLED)
            self.assertEqual(len(engine._image_provider_override.calls), 1)
            self.assertTrue((context.folder("images") / "image_01.png").is_file())
            self.assertFalse((context.folder("images") / "image_02.png").is_file())
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeImageProvider(ready_error="Forge is unreachable at http://127.0.0.1:7860")
            engine, context = _engine(Path(tmp), fake)
            result = engine.generate_images(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertTrue(any("unreachable" in err.casefold() for err in result.errors))
            self.assertEqual(fake.calls, [])
            self.assertFalse(any((context.project_dir / "images").glob("image_*.png")))


class ImagesFolderResolutionTests(unittest.TestCase):
    def test_prefers_images_over_legacy_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            (root / "image").mkdir()
            resolved = resolve_images_dir(root)
            self.assertEqual(resolved.name, "images")

    def test_uses_legacy_image_when_only_legacy_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image").mkdir()
            resolved = resolve_images_dir(root)
            self.assertEqual(resolved.name, "image")

    def test_creates_images_when_neither_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = resolve_images_dir(root)
            self.assertEqual(resolved.name, "images")
            self.assertTrue(resolved.is_dir())
            self.assertFalse((root / "image").exists())
