"""Integration tests for Voice Service / Pipeline (Sprint 11 component 5)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.artifacts import ArtifactKind, ArtifactResolver
from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.pipelines.context import ChannelDefaults
from app.pipelines.engine import ProductionEngine
from app.pipelines.results import PipelineOutcome
from app.pipelines.voice_pipeline import VoicePipeline
from app.projects.project_service import ProjectService
from app.providers.errors import ProviderError
from app.providers.voice_base import (
    VoiceInfo,
    VoiceProvider,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)
from app.voice.manifest import VoiceManifest
from app.voice.naming import VOICE_BASENAME, VOICE_FOLDER, voice_manifest_path, voice_path


class FakeVoiceProvider(VoiceProvider):
    def __init__(
        self,
        *,
        fail: bool = False,
        audio: bytes = b"RIFF-FAKE-WAV",
    ) -> None:
        self.calls: list[VoiceSynthesisRequest] = []
        self._fail = fail
        self._audio = audio
        self.block_until_cancel: VoicePipeline | None = None

    @property
    def provider_id(self) -> str:
        return "fake-voice"

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        self.calls.append(request)
        if self.block_until_cancel is not None:
            self.block_until_cancel.cancel()
        if self._fail:
            raise ProviderError("simulated voice failure")
        return VoiceSynthesisResponse(
            audio_bytes=self._audio,
            content_type="audio/wav",
            model=request.model or "fake-model",
            voice_id=request.voice_id or "voice-1",
            generation_time_ms=4.0,
        )

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(voice_id="voice-1", name="Narrator")]

    def list_models(self) -> list[str]:
        return ["fake-model"]

    def test_connection(self) -> str:
        return "Fake OK"

    def validate_ready(self) -> None:
        return None


def _engine(tmp: Path, provider: VoiceProvider) -> tuple[ProductionEngine, object]:
    data_root = tmp / "atlas"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    config.voice_provider = "local"
    config.voice.voice_id = "af_heart"
    config.voice.voice_name = "Heart"
    config.voice.speed = 1.1
    Storage(config).ensure_structure()
    projects = ProjectService(config)
    project = projects.create_project(channel, "Atlantis")
    engine = ProductionEngine(projects, config, voice_provider=provider)
    context = engine.build_context(
        project,
        channel_defaults=ChannelDefaults(name=channel),
    )
    script = context.folder("script") / "narration.md"
    script.write_text(
        "Welcome to Atlantis.\n\nThe harbor lights still burn.",
        encoding="utf-8",
    )
    return engine, context


class VoiceServicePipelineTests(unittest.TestCase):
    def test_generate_voice_writes_wav_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider(audio=b"RIFFVOICE")
            engine, context = _engine(Path(tmp), fake)
            stages: list[str] = []
            seen: list[tuple[int, int, str, str]] = []

            def on_progress(c: int, t: int, m: str, d: str = "") -> None:
                seen.append((c, t, m, d))
                stages.append(m)

            result = engine.generate_voice(context, on_queue_progress=on_progress)

            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            out = voice_path(context.project_dir)
            self.assertEqual(out.parent.name, VOICE_FOLDER)
            self.assertEqual(out.name, VOICE_BASENAME)
            self.assertTrue(out.is_file())
            self.assertEqual(out.read_bytes(), b"RIFFVOICE")
            self.assertTrue(voice_manifest_path(context.project_dir).is_file())

            loaded = VoiceManifest.read_json(voice_manifest_path(context.project_dir))
            self.assertTrue(loaded.exported)
            self.assertEqual(loaded.provider_id, "fake-voice")
            self.assertEqual(loaded.voice_id, "af_heart")
            self.assertEqual(loaded.full_text, fake.calls[0].text)
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(fake.calls[0].voice_id, "af_heart")
            self.assertEqual(fake.calls[0].speed, 1.1)
            self.assertEqual(fake.calls[0].output_format, "wav")

            self.assertTrue(any(a.endswith(VOICE_BASENAME) for a in result.artifacts))
            self.assertTrue(any("voice_manifest.json" in a for a in result.artifacts))
            self.assertTrue(any(item[2] == "Generating voice" for item in seen))
            self.assertIn("Voice planned", stages)
            self.assertIn("Voice complete", stages)

            found = ArtifactResolver(context.project_dir).find(ArtifactKind.VOICE)
            self.assertEqual(found, out)

            progress = engine._projects.get_progress(
                context.channel_name,
                context.project_name,
            )
            self.assertTrue(progress.step("voice").complete)

    def test_regenerate_voice_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider(audio=b"FIRST")
            engine, context = _engine(Path(tmp), fake)
            engine.generate_voice(context)
            fake2 = FakeVoiceProvider(audio=b"SECOND")
            engine2 = ProductionEngine(
                engine._projects,
                engine._config,
                voice_provider=fake2,
            )
            result = engine2.regenerate_voice(context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(voice_path(context.project_dir).read_bytes(), b"SECOND")

    def test_cancel_during_synthesis_keeps_file_and_returns_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider()
            engine, context = _engine(Path(tmp), fake)
            pipeline = VoicePipeline(fake, engine._config.voice)
            fake.block_until_cancel = pipeline
            result = engine.execute(pipeline, context)
            self.assertEqual(result.outcome, PipelineOutcome.CANCELLED)
            self.assertTrue(voice_path(context.project_dir).is_file())


if __name__ == "__main__":
    unittest.main()
