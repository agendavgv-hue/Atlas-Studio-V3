"""Sprint 7 — Voice Pipeline tests (fake ElevenLabs only)."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from app.artifacts import ArtifactKind, ArtifactResolver
from app.artifacts.documents import read_document_text
from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.pipelines.context import ChannelDefaults
from app.pipelines.engine import ProductionEngine
from app.pipelines.results import PipelineOutcome
from app.pipelines.voice_info import format_duration_ms, format_file_size, voice_file_info
from app.pipelines.voice_naming import resolve_mp3_dir, voice_basename
from app.pipelines.voice_pipeline import VoicePipeline
from app.projects.project_service import ProjectService
from app.providers.errors import ProviderError
from app.providers.local_voice import LOCAL_VOICE_PROVIDER_LABEL, LocalVoiceProvider
from app.providers.voice_base import (
    VoiceInfo,
    VoiceProvider,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)


class FakeVoiceProvider(VoiceProvider):
    """Test-only provider."""

    def __init__(
        self,
        *,
        fail: bool = False,
        ready_error: str | None = None,
        audio: bytes = b"ID3FAKEMP3",
    ) -> None:
        self.calls: list[VoiceSynthesisRequest] = []
        self._fail = fail
        self._ready_error = ready_error
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
            content_type="audio/mpeg",
            model="fake-model",
            voice_id="voice-1",
            generation_time_ms=9.5,
        )

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(voice_id="voice-1", name="Narrator")]

    def list_models(self) -> list[str]:
        return ["fake-model"]

    def test_connection(self) -> str:
        if self._ready_error:
            raise ProviderError(self._ready_error)
        return "Fake OK"

    def validate_ready(self) -> None:
        if self._ready_error:
            raise ProviderError(self._ready_error)


def _engine(tmp: Path, provider: VoiceProvider) -> tuple[ProductionEngine, object]:
    data_root = tmp / "atlas"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    config.voice_provider = "local"
    config.voice.voice_id = "local_default"
    config.voice.voice_name = "Default"
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


def _write_docx(path: Path, text: str) -> None:
    document = ElementTree.Element(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document"
    )
    body = ElementTree.SubElement(
        document, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body"
    )
    paragraph = ElementTree.SubElement(
        body, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
    )
    run = ElementTree.SubElement(
        paragraph, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r"
    )
    node = ElementTree.SubElement(
        run, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
    )
    node.text = text
    xml = ElementTree.tostring(document, encoding="utf-8", xml_declaration=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", xml)


class LocalVoiceEngineTests(unittest.TestCase):
    def test_public_label_does_not_expose_backend_name(self) -> None:
        self.assertIn("Local Voice Engine", LOCAL_VOICE_PROVIDER_LABEL)
        self.assertNotIn("Kokoro", LOCAL_VOICE_PROVIDER_LABEL)
        self.assertNotIn("kokoro", LOCAL_VOICE_PROVIDER_LABEL.casefold())

    def test_missing_backend_message_is_product_facing(self) -> None:
        provider = LocalVoiceProvider(AppConfig(data_root=Path(".")).voice)
        with self.assertRaises(ProviderError) as raised:
            provider.test_connection()
        message = str(raised.exception)
        self.assertIn("Local Voice Engine", message)
        self.assertIn("Python 3.13", message)
        self.assertNotIn("Kokoro", message)

    def test_voice_basename_from_content_type(self) -> None:
        self.assertEqual(voice_basename("audio/mpeg"), "voice.mp3")
        self.assertEqual(voice_basename("audio/wav"), "voice.wav")


class DocumentReaderTests(unittest.TestCase):
    def test_reads_txt_md_docx_rtf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("plain text", encoding="utf-8")
            (root / "b.md").write_text("# Title\nBody", encoding="utf-8")
            _write_docx(root / "c.docx", "Docx narration")
            (root / "d.rtf").write_text(
                r"{\rtf1\ansi Hello RTF world}",
                encoding="utf-8",
            )
            self.assertIn("plain", read_document_text(root / "a.txt"))
            self.assertIn("Body", read_document_text(root / "b.md"))
            self.assertIn("Docx narration", read_document_text(root / "c.docx"))
            self.assertIn("Hello", read_document_text(root / "d.rtf"))


class VoiceInfoTests(unittest.TestCase):
    def test_formats_size_and_duration(self) -> None:
        self.assertEqual(format_file_size(1536), "1.5 KB")
        self.assertEqual(format_duration_ms(125_000), "2:05")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "voice.mp3"
            path.write_bytes(b"x" * 2048)
            info = voice_file_info(path, duration_ms=65_000)
            assert info is not None
            self.assertIn("1:05", info.summary)
            self.assertIn("KB", info.summary)


class VoicePipelineTests(unittest.TestCase):
    def test_generate_writes_voice_mp3_and_refreshes_intelligence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider(audio=b"ID3VOICE")
            engine, context = _engine(Path(tmp), fake)
            seen: list[tuple[int, int, str, str]] = []

            result = engine.generate_voice(
                context,
                on_queue_progress=lambda c, t, m, d="": seen.append((c, t, m, d)),
            )

            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(result.queue_total, 1)
            self.assertTrue(seen)
            self.assertTrue(any(item[2] == "Generating voice" for item in seen))
            out = context.folder("mp3") / voice_basename()
            self.assertTrue(out.is_file())
            self.assertEqual(out.read_bytes(), b"ID3VOICE")
            self.assertEqual(len(fake.calls), 1)
            self.assertIn("Atlantis", fake.calls[0].text)

            progress = engine._projects.get_progress(
                context.channel_name,
                context.project_name,
            )
            self.assertTrue(progress.step("voice").complete)
            found = ArtifactResolver(context.project_dir).find(ArtifactKind.VOICE)
            self.assertEqual(found, out)

    def test_script_discovery_via_resolver_not_hardcoded_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider()
            engine, context = _engine(Path(tmp), fake)
            script_dir = context.folder("script")
            (script_dir / "narration.md").unlink()
            (script_dir / "episode_screenplay.txt").write_text(
                "Narration from renamed script.",
                encoding="utf-8",
            )
            result = engine.generate_voice(context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertIn("renamed script", fake.calls[0].text)

    def test_docx_script_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider()
            engine, context = _engine(Path(tmp), fake)
            script_dir = context.folder("script")
            (script_dir / "narration.md").unlink()
            _write_docx(script_dir / "story.docx", "Spoken from DOCX.")
            result = engine.generate_voice(context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertIn("DOCX", fake.calls[0].text)

    def test_missing_script_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider()
            engine, context = _engine(Path(tmp), fake)
            for path in (context.folder("script")).glob("*"):
                if path.is_file():
                    path.unlink()
            result = engine.generate_voice(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertTrue(any("script" in err.casefold() for err in result.errors))

    def test_missing_local_backend_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "atlas"
            project_root = Path(tmp) / "youtube"
            channel = "Hollow Atlas"
            (project_root / channel).mkdir(parents=True)
            config = AppConfig(data_root=data_root, project_root=project_root)
            # Default free-first path: Local Voice Engine (currently postponed).
            config.voice_provider = None
            Storage(config).ensure_structure()
            projects = ProjectService(config)
            project = projects.create_project(channel, "Atlantis")
            engine = ProductionEngine(projects, config)
            context = engine.build_context(project)
            (context.folder("script") / "script.txt").write_text("Hi", encoding="utf-8")
            result = engine.generate_voice(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            joined = " ".join(result.errors).casefold()
            self.assertIn("local voice", joined)
            self.assertIn("python 3.13", joined)
            self.assertNotIn("elevenlabs", joined)

    def test_registry_defaults_to_local(self) -> None:
        from app.providers.local_voice import LOCAL_VOICE_PROVIDER_ID
        from app.providers.voice_registry import VoiceProviderRegistry

        config = AppConfig(data_root=Path("."))
        config.voice_provider = None
        provider = VoiceProviderRegistry(config).require_voice_provider()
        self.assertEqual(provider.provider_id, LOCAL_VOICE_PROVIDER_ID)

    def test_provider_failure_returns_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider(fail=True)
            engine, context = _engine(Path(tmp), fake)
            result = engine.generate_voice(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertFalse((context.folder("mp3") / voice_basename()).is_file())

    def test_cancel_during_synthesis_keeps_file_and_returns_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider()
            engine, context = _engine(Path(tmp), fake)
            pipeline = VoicePipeline(fake)
            fake.block_until_cancel = pipeline
            result = engine.execute(pipeline, context)
            self.assertEqual(result.outcome, PipelineOutcome.CANCELLED)
            self.assertTrue((context.folder("mp3") / voice_basename()).is_file())

    def test_validate_ready_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeVoiceProvider(ready_error="API Key invalid")
            engine, context = _engine(Path(tmp), fake)
            result = engine.generate_voice(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertIn("API Key invalid", result.errors[0])

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
            self.assertEqual(
                (context.folder("mp3") / voice_basename()).read_bytes(),
                b"SECOND",
            )

    def test_mp3_folder_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mp3").mkdir()
            self.assertEqual(resolve_mp3_dir(root).name, "mp3")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "audio").mkdir()
            self.assertEqual(resolve_mp3_dir(root).name, "audio")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = resolve_mp3_dir(root)
            self.assertEqual(resolved.name, "mp3")
            self.assertTrue(resolved.is_dir())


class VoiceArtifactTests(unittest.TestCase):
    def test_resolver_finds_voice_by_purpose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mp3").mkdir()
            (root / "mp3" / "voice.mp3").write_bytes(b"a")
            (root / "mp3" / "other.wav").write_bytes(b"b")
            found = ArtifactResolver(root).find(ArtifactKind.VOICE)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.name, "voice.mp3")

    def test_legacy_audio_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "audio").mkdir()
            (root / "audio" / "narration.mp3").write_bytes(b"x")
            self.assertTrue(ArtifactResolver(root).exists(ArtifactKind.VOICE))


if __name__ == "__main__":
    unittest.main()
