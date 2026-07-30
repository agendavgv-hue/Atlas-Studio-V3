"""Unit tests for VoiceGenerator (Sprint 11 component 4)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.pipelines.context import ChannelDefaults, PipelineContext
from app.projects.models import Project
from app.providers.errors import ProviderError
from app.providers.voice_base import (
    VoiceInfo,
    VoiceProvider,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)
from app.voice.generator import VoiceGenerator
from app.voice.manifest import VoiceManifest
from app.voice.plan import VoicePlan, VoiceSegment
from app.voice.planner import VoicePlanner


class _FakeVoiceProvider(VoiceProvider):
    def __init__(self, *, empty: bool = False) -> None:
        self.calls: list[VoiceSynthesisRequest] = []
        self._empty = empty

    @property
    def provider_id(self) -> str:
        return "fake-voice"

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        self.calls.append(request)
        if self._empty:
            return VoiceSynthesisResponse(audio_bytes=b"", content_type="audio/wav")
        return VoiceSynthesisResponse(
            audio_bytes=b"RIFF-fake-wav",
            content_type="audio/wav",
            model=request.model or "fake-model",
            voice_id=request.voice_id or "fake-voice-id",
            generation_time_ms=12.5,
        )

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo("fake-voice-id", "Fake", "en-US")]

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


def _manifest_from_script(script: str = "Hello Atlas.") -> VoiceManifest:
    plan = VoicePlanner().plan(script)
    return VoiceManifest.from_plan(
        plan,
        provider_id="fake-voice",
        voice_id="af_heart",
        voice_name="Heart",
        model="demo-model",
        speed=1.25,
        stability=0.4,
        style=0.1,
        similarity=0.8,
    )


class VoiceGeneratorTests(unittest.TestCase):
    def test_builds_request_exclusively_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = _FakeVoiceProvider()
            manifest = _manifest_from_script("Narrate this exactly.")
            result = VoiceGenerator().generate(
                manifest,
                provider,
                _context(Path(tmp)),
            )

            self.assertEqual(len(provider.calls), 1)
            request = provider.calls[0]
            self.assertEqual(request.text, manifest.full_text)
            self.assertEqual(request.voice_id, "af_heart")
            self.assertEqual(request.language, manifest.language)
            self.assertEqual(request.model, "demo-model")
            self.assertEqual(request.speed, 1.25)
            self.assertEqual(request.stability, 0.4)
            self.assertEqual(request.style, 0.1)
            self.assertEqual(request.similarity, 0.8)
            self.assertEqual(request.output_format, "wav")
            self.assertEqual(result.audio_bytes, b"RIFF-fake-wav")
            self.assertEqual(result.provider_id, "fake-voice")
            self.assertEqual(result.content_type, "audio/wav")

    def test_does_not_rewrite_segment_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = _FakeVoiceProvider()
            plan = VoicePlan(
                segments=(VoiceSegment(index=1, text="Keep this wording."),),
                language="en-US",
                estimated_duration_sec=1.0,
                rationale="test",
            )
            manifest = VoiceManifest.from_plan(plan, voice_id="v1", speed=1.0)
            VoiceGenerator().generate(manifest, provider, _context(Path(tmp)))
            self.assertEqual(provider.calls[0].text, "Keep this wording.")

    def test_rejects_empty_manifest_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = VoiceManifest(segments=[], voice_id="v1")
            with self.assertRaises(ProviderError):
                VoiceGenerator().generate(
                    manifest,
                    _FakeVoiceProvider(),
                    _context(Path(tmp)),
                )

    def test_rejects_empty_provider_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ProviderError):
                VoiceGenerator().generate(
                    _manifest_from_script(),
                    _FakeVoiceProvider(empty=True),
                    _context(Path(tmp)),
                )

    def test_provider_agnostic_interface_only(self) -> None:
        """Any VoiceProvider works — no Kokoro/ElevenLabs imports in generator."""
        import app.voice.generator as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("kokoro", source.lower())
        self.assertNotIn("elevenlabs", source.lower())
        self.assertIn("VoiceProvider", source)
        self.assertIn("VoiceSynthesisRequest", source)


if __name__ == "__main__":
    unittest.main()
