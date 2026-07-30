"""End-to-end workflow: Script → Production → Images → Voice → Movie → Thumbnail → Shorts.

Validates the canonical Production Sheet contract across every consumer.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.artifacts import ArtifactKind, ArtifactResolver
from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.pipelines.artifacts import PRODUCTION_SHEET_FILENAME, SCRIPT_FOLDER
from app.pipelines.context import ChannelDefaults
from app.pipelines.engine import ProductionEngine
from app.pipelines.image_naming import image_basename
from app.pipelines.results import PipelineOutcome
from app.pipelines.sheet_format import CANONICAL_SHEET_EXAMPLE
from app.pipelines.sheet_prompts import extract_image_prompts, extract_sheet_durations
from app.projects.project_service import ProjectService
from app.providers.base import TextProvider
from app.providers.image_base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)
from app.providers.voice_base import (
    VoiceInfo,
    VoiceProvider,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)
from app.render.naming import final_video_path
from app.shorts.naming import short_path, shorts_manifest_path
from app.shorts.settings import ShortsSettings
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.naming import thumbnail_path
from app.thumbnail.settings import ThumbnailSettings
from app.voice.naming import voice_manifest_path, voice_path
from tests.test_sprint8_movie_pipeline import FakeFFmpeg


class _E2EText(TextProvider):
    @property
    def provider_id(self) -> str:
        return "e2e-text"

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        blob = f"{system or ''}\n{prompt}".casefold()
        if "image 01" in blob or "production sheet" in blob or "convert the narration" in blob:
            return CANONICAL_SHEET_EXAMPLE
        return (
            "Welcome to Atlantis under the waves.\n\n"
            "Ancient towers still gleam in the deep."
        )


class _E2EImage(ImageProvider):
    def __init__(self) -> None:
        self.n = 0

    @property
    def provider_id(self) -> str:
        return "e2e-image"

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self.n += 1
        return ImageGenerationResponse(
            image_png=b"\x89PNG\r\n\x1a\n" + f"img{self.n}".encode(),
            seed=self.n,
            model="e2e",
            width=512,
            height=512,
        )

    def list_models(self) -> list[str]:
        return ["e2e"]

    def test_connection(self) -> str:
        return "ok"

    def validate_ready(self) -> None:
        return None


class _E2EVoice(VoiceProvider):
    @property
    def provider_id(self) -> str:
        return "e2e-voice"

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        return VoiceSynthesisResponse(
            audio_bytes=b"RIFF....WAVEfmt " + request.text[:20].encode(),
            content_type="audio/wav",
            voice_id=request.voice_id or "af_heart",
            model="e2e",
        )

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo("af_heart", "Heart", "en-US")]

    def list_models(self) -> list[str]:
        return ["e2e"]

    def test_connection(self) -> str:
        return "ok"

    def validate_ready(self) -> None:
        return None


class FullProductionWorkflowTests(unittest.TestCase):
    def test_script_through_shorts_uses_shared_sheet_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "atlas"
            project_root = root / "youtube"
            channel = "Hollow Atlas"
            (project_root / channel).mkdir(parents=True)
            config = AppConfig(data_root=data_root, project_root=project_root)
            config.image_provider = "forge"
            config.voice_provider = "kokoro"
            config.voice.voice_id = "af_heart"
            Storage(config).ensure_structure()
            projects = ProjectService(config)
            project = projects.create_project(channel, "Atlantis")

            ffmpeg = FakeFFmpeg(voice_duration=12.0)
            engine = ProductionEngine(
                projects,
                config,
                text_provider=_E2EText(),
                image_provider=_E2EImage(),
                voice_provider=_E2EVoice(),
                ffmpeg=ffmpeg,
            )
            context = engine.build_context(
                project,
                channel_defaults=ChannelDefaults(
                    name=channel,
                    image_prompt="cinematic",
                    thumbnail_prompt="",  # select mode from images
                ),
            )

            # 1) Script → Production Sheet
            production = engine.generate_production(context)
            self.assertEqual(production.outcome, PipelineOutcome.SUCCESS, production.errors)
            sheet_path = context.folder(SCRIPT_FOLDER) / PRODUCTION_SHEET_FILENAME
            self.assertTrue(sheet_path.is_file())
            sheet_text = sheet_path.read_text(encoding="utf-8")
            prompts = extract_image_prompts(sheet_text)
            self.assertEqual(len(prompts), 3)
            self.assertEqual(extract_sheet_durations(sheet_text, 3), [5.0, 4.0, 3.0])

            # 2) Images
            images = engine.generate_images(context)
            self.assertEqual(images.outcome, PipelineOutcome.SUCCESS, images.errors)
            self.assertEqual(images.queue_total, 3)
            for index in (1, 2, 3):
                self.assertTrue(
                    (context.folder("images") / image_basename(index)).is_file()
                )

            # 3) Voice
            voice = engine.generate_voice(context)
            self.assertEqual(voice.outcome, PipelineOutcome.SUCCESS, voice.errors)
            self.assertTrue(voice_path(context.project_dir).is_file())
            self.assertTrue(voice_manifest_path(context.project_dir).is_file())

            # 4) Movie
            movie = engine.generate_movie(context)
            self.assertEqual(movie.outcome, PipelineOutcome.SUCCESS, movie.errors)
            self.assertTrue(final_video_path(context.project_dir).is_file())

            # 5) Thumbnail (select from generated images)
            thumb = engine.generate_thumbnail(
                context,
                settings=ThumbnailSettings(mode=ThumbnailMode.SELECT.value),
            )
            self.assertEqual(thumb.outcome, PipelineOutcome.SUCCESS, thumb.errors)
            self.assertTrue(thumbnail_path(context.project_dir).is_file())

            # 6) Shorts
            shorts = engine.generate_shorts(
                context,
                settings=ShortsSettings(max_shorts=1, motion="none"),
            )
            self.assertEqual(shorts.outcome, PipelineOutcome.SUCCESS, shorts.errors)
            self.assertTrue(short_path(context.project_dir, 1).is_file())
            self.assertTrue(shorts_manifest_path(context.project_dir).is_file())

            resolver = ArtifactResolver(context.project_dir)
            self.assertTrue(resolver.exists(ArtifactKind.SCRIPT))
            self.assertTrue(resolver.exists(ArtifactKind.PRODUCTION_SHEET))
            self.assertTrue(resolver.exists(ArtifactKind.IMAGES))
            self.assertTrue(resolver.exists(ArtifactKind.VOICE))
            self.assertTrue(resolver.exists(ArtifactKind.YOUTUBE_EXPORT))
            self.assertTrue(resolver.exists(ArtifactKind.THUMBNAIL))

            progress = projects.get_progress(channel, project.folder_name)
            for key in (
                "script",
                "production_sheet",
                "images",
                "voice",
                "movie",
                "thumbnail",
                "shorts",
            ):
                step = progress.step(key)
                self.assertIsNotNone(step, msg=key)
                assert step is not None
                self.assertTrue(step.complete, msg=key)


class SharedSheetParserGuardTests(unittest.TestCase):
    def test_no_private_image_header_parsers_outside_sheet_prompts(self) -> None:
        """Downstream modules must not redefine IMAGE header regexes."""
        repo = Path(__file__).resolve().parents[1]
        roots = [
            repo / "app" / "shorts",
            repo / "app" / "render",
            repo / "app" / "thumbnail",
            repo / "app" / "voice",
            repo / "app" / "pipelines" / "image_pipeline.py",
            repo / "app" / "pipelines" / "movie_pipeline.py",
            repo / "app" / "pipelines" / "shorts_pipeline.py",
            repo / "app" / "pipelines" / "thumbnail_pipeline.py",
            repo / "app" / "pipelines" / "voice_pipeline.py",
        ]
        offenders: list[str] = []
        for root in roots:
            files = [root] if root.is_file() else list(root.rglob("*.py"))
            for file in files:
                if not file.is_file() or file.name == "sheet_prompts.py":
                    continue
                text = file.read_text(encoding="utf-8")
                if "(?:IMAGE|Scene)" in text or "_IMAGE_HEADER" in text:
                    offenders.append(str(file.relative_to(repo)))
        self.assertEqual(offenders, [], msg=f"Private sheet parsers found: {offenders}")


if __name__ == "__main__":
    unittest.main()
