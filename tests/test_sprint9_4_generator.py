"""Unit tests for ThumbnailGenerator (Sprint 9 component 4)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.pipelines.context import ChannelDefaults, PipelineContext
from app.projects.models import Project
from app.providers.errors import ProviderError
from app.providers.image_base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)
from app.thumbnail.generator import ThumbnailGenerator
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.selector import SelectionDecision, SelectionGenerationSettings


class _FakeImageProvider(ImageProvider):
    def __init__(self) -> None:
        self.calls: list[ImageGenerationRequest] = []

    @property
    def provider_id(self) -> str:
        return "fake"

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self.calls.append(request)
        return ImageGenerationResponse(
            image_png=b"\x89PNG-generated",
            seed=7,
            model=request.model or "fake-model",
            width=request.width or 1280,
            height=request.height or 720,
            generation_time_ms=1.5,
        )

    def list_models(self) -> list[str]:
        return ["fake-model"]

    def test_connection(self) -> str:
        return "ok"


def _context(root: Path) -> PipelineContext:
    project = Project.create_default(name="Demo", channel_name="Hollow Atlas")
    return PipelineContext(
        project=project,
        project_dir=root,
        channel_defaults=ChannelDefaults(name="Hollow Atlas"),
    )


def _decision(
    *,
    mode: ThumbnailMode,
    source: Path | None = None,
    prompt: str = "",
) -> SelectionDecision:
    return SelectionDecision(
        mode=mode,
        source_image_path=source,
        prompt=prompt,
        negative_prompt="",
        generation=SelectionGenerationSettings(width=1280, height=720),
        rationale="test",
    )


class ThumbnailGeneratorTests(unittest.TestCase):
    def test_generate_mode_uses_provider_framework_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provider = _FakeImageProvider()
            request = ImageGenerationRequest(
                prompt="epic thumbnail",
                negative_prompt="blurry",
                width=1280,
                height=720,
                seed=3,
                model="demo",
            )
            result = ThumbnailGenerator(provider).generate(
                _decision(mode=ThumbnailMode.GENERATE, prompt="epic thumbnail"),
                request,
                _context(root),
            )
            self.assertEqual(result.image_png, b"\x89PNG-generated")
            self.assertEqual(result.provider_id, "fake")
            self.assertEqual(result.seed, 7)
            self.assertEqual(len(provider.calls), 1)
            self.assertEqual(provider.calls[0].prompt, "epic thumbnail")

    def test_select_mode_loads_source_without_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "images" / "image_02.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"\x89PNG-source")
            result = ThumbnailGenerator(None).generate(
                _decision(mode=ThumbnailMode.SELECT, source=source),
                None,
                _context(root),
            )
            self.assertEqual(result.image_png, b"\x89PNG-source")
            self.assertEqual(result.provider_id, "")

    def test_generate_without_request_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ProviderError):
                ThumbnailGenerator(_FakeImageProvider()).generate(
                    _decision(mode=ThumbnailMode.GENERATE, prompt="x"),
                    None,
                    _context(Path(tmp)),
                )

    def test_does_not_write_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "images" / "a.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"data")
            ThumbnailGenerator().generate(
                _decision(mode=ThumbnailMode.SELECT, source=source),
                None,
                _context(root),
            )
            self.assertFalse((root / "thumbnail").exists())
            self.assertEqual(list((root / "images").iterdir()), [source])


if __name__ == "__main__":
    unittest.main()
