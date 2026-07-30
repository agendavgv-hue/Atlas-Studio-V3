"""Unit tests for ShortsGenerator (Sprint 10 component 5)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.movie_settings import RENDER_PROFILES
from app.pipelines.context import ChannelDefaults, PipelineContext
from app.projects.models import Project
from app.providers.errors import ProviderError
from app.render.renderer import FFmpegRenderer
from app.shorts.definition import ShortsDefinition, ShortsScene, ShortsVoicePlan
from app.shorts.generator import ShortsGenerator
from tests.test_sprint8_movie_pipeline import FakeFFmpeg


def _context(root: Path) -> PipelineContext:
    project = Project.create_default(name="Demo", channel_name="Hollow Atlas")
    return PipelineContext(
        project=project,
        project_dir=root,
        channel_defaults=ChannelDefaults(name="Hollow Atlas"),
    )


def _definition(images: list[Path], *, voice: Path | None = None) -> ShortsDefinition:
    scenes = [
        ShortsScene(
            index=i,
            image_path=str(path),
            duration_sec=2.0,
            motion="none",
        )
        for i, path in enumerate(images, start=1)
    ]
    voice_plan = ShortsVoicePlan(use_voice=False)
    if voice is not None:
        voice_plan = ShortsVoicePlan(use_voice=True, voice_path=str(voice))
    return ShortsDefinition.create(
        index=1,
        scenes=scenes,
        voice=voice_plan,
        total_duration_sec=2.0 * len(scenes),
    )


class ShortsGeneratorTests(unittest.TestCase):
    def test_renders_via_ffmpeg_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = []
            for i in (1, 2):
                path = root / f"image_{i:02d}.png"
                path.write_bytes(b"png")
                images.append(path)
            fake = FakeFFmpeg()
            generator = ShortsGenerator(fake, renderer=FFmpegRenderer(fake))
            result = generator.generate(
                _definition(images),
                _context(root),
                RENDER_PROFILES["shorts"],
            )
            self.assertTrue(result.video_bytes)
            self.assertTrue(result.definition_id)
            # Scene encodes + final concat (no project short/ written).
            self.assertGreaterEqual(len(fake.calls), 3)
            self.assertFalse((root / "short").exists())

    def test_uses_voice_when_planned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "image_01.png"
            image.write_bytes(b"png")
            voice = root / "voice.mp3"
            voice.write_bytes(b"ID3")
            fake = FakeFFmpeg()
            ShortsGenerator(fake).generate(
                _definition([image], voice=voice),
                _context(root),
                RENDER_PROFILES["shorts"],
            )
            joined = [" ".join(call) for call in fake.calls]
            self.assertTrue(any("voice.mp3" in item or str(voice) in item for item in joined))

    def test_rejects_empty_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ProviderError):
                ShortsGenerator(FakeFFmpeg()).generate(
                    ShortsDefinition.create(index=1, scenes=[]),
                    _context(root),
                    RENDER_PROFILES["shorts"],
                )

    def test_does_not_write_canonical_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "image_01.png"
            image.write_bytes(b"png")
            ShortsGenerator(FakeFFmpeg()).generate(
                _definition([image]),
                _context(root),
                RENDER_PROFILES["shorts"],
            )
            self.assertFalse((root / "short" / "short_01.mp4").exists())


if __name__ == "__main__":
    unittest.main()
