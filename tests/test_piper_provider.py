"""PiperVoiceProvider — folder-scanned local ONNX TTS."""

from __future__ import annotations

import io
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from app.core.app_config import AppConfig
from app.core.voice_settings import VoiceSettings
from app.providers.errors import ProviderError
from app.providers.piper import (
    PIPER_PROVIDER_ID,
    PiperVoiceProvider,
    _display_name_from_piper_stem,
    resolve_piper_voices_dir,
)
from app.providers.voice_base import VoiceSynthesisRequest
from app.providers.voice_discovery import VoiceDiscoveryService
from app.providers.voice_registry import VoiceProviderRegistry
from app.voice.generator import synthesize_with_provider


class _FakePiperVoice:
    """Mirrors current piper-tts: synthesize_wav + chunk synthesize."""

    def __init__(self) -> None:
        self.config = types.SimpleNamespace(sample_rate=22050)
        self.calls: list[str] = []

    @classmethod
    def load(cls, model_path: str, config_path: str | None = None, **_kwargs):
        del model_path, config_path
        return cls()

    def synthesize_wav(self, text: str, wav_file, syn_config=None, **_kwargs):
        del syn_config, _kwargs
        self.calls.append(text)
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 100)

    def synthesize(self, text: str, syn_config=None, **_kwargs):
        del syn_config, _kwargs
        self.calls.append(f"chunk:{text}")
        yield types.SimpleNamespace(
            sample_rate=22050,
            sample_width=2,
            sample_channels=1,
            audio_int16_bytes=b"\x00\x00" * 50,
        )


class _LegacyFakePiperVoice:
    """Older piper API used in some installs."""

    def __init__(self) -> None:
        self.config = types.SimpleNamespace(sample_rate=22050)

    @classmethod
    def load(cls, model_path: str, config_path: str | None = None, **_kwargs):
        del model_path, config_path
        return cls()

    def synthesize_stream_raw(self, text: str, **_kwargs):
        del text, _kwargs
        yield b"\x00\x00" * 100


def _install_fake_piper(voice_cls=None):
    voice_cls = voice_cls or _FakePiperVoice
    voice_mod = types.ModuleType("piper.voice")
    voice_mod.PiperVoice = voice_cls  # type: ignore[attr-defined]
    piper_mod = types.ModuleType("piper")
    piper_mod.voice = voice_mod  # type: ignore[attr-defined]
    return patch.dict(
        sys.modules,
        {"piper": piper_mod, "piper.voice": voice_mod},
    )


class PiperHelperTests(unittest.TestCase):
    def test_display_name_from_stem(self) -> None:
        self.assertEqual(
            _display_name_from_piper_stem("en_US-lessac-medium"),
            "Lessac Medium",
        )

    def test_ensure_piper_voices_dir_creates_folder(self) -> None:
        from app.providers.piper import ensure_piper_voices_dir

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = ensure_piper_voices_dir(root)
            self.assertTrue(path.is_dir())
            self.assertEqual(path, (root / "voices" / "piper").resolve())


class PiperProviderTests(unittest.TestCase):
    def test_list_voices_scans_onnx_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            voices_dir = Path(tmp)
            (voices_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake")
            (voices_dir / "nl_NL-rdh-medium.onnx").write_bytes(b"fake")
            (voices_dir / "readme.txt").write_text("ignore", encoding="utf-8")
            provider = PiperVoiceProvider(VoiceSettings(), voices_dir=voices_dir)
            with _install_fake_piper():
                voices = provider.list_voices()
            ids = {v.voice_id for v in voices}
            self.assertEqual(ids, {"en_US-lessac-medium", "nl_NL-rdh-medium"})
            lessac = next(v for v in voices if v.voice_id.startswith("en_US"))
            self.assertEqual(lessac.language, "en-US")
            self.assertEqual(lessac.name, "Lessac Medium")

    def test_list_voices_raises_when_folder_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = PiperVoiceProvider(VoiceSettings(), voices_dir=Path(tmp))
            with _install_fake_piper():
                with self.assertRaises(ProviderError) as ctx:
                    provider.list_voices()
            self.assertIn("No Piper", str(ctx.exception))

    def test_synthesize_returns_wav(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            voices_dir = Path(tmp)
            (voices_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake")
            provider = PiperVoiceProvider(
                VoiceSettings(voice_id="en_US-lessac-medium"),
                voices_dir=voices_dir,
            )
            with _install_fake_piper():
                response = synthesize_with_provider(
                    provider,
                    VoiceSynthesisRequest(
                        text="Hello from Piper.",
                        voice_id="en_US-lessac-medium",
                    ),
                )
            self.assertEqual(response.voice_id, "en_US-lessac-medium")
            self.assertTrue(response.audio_bytes.startswith(b"RIFF"))
            self.assertEqual(response.content_type, "audio/wav")
            with wave.open(io.BytesIO(response.audio_bytes), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 1)
                self.assertEqual(wav.getsampwidth(), 2)

    def test_synthesize_requires_selected_voice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            voices_dir = Path(tmp)
            (voices_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake")
            provider = PiperVoiceProvider(VoiceSettings(), voices_dir=voices_dir)
            with _install_fake_piper():
                with self.assertRaises(ProviderError) as ctx:
                    provider.synthesize(VoiceSynthesisRequest(text="Hello"))
            self.assertEqual(str(ctx.exception), "No Piper voice selected.")

    def test_synthesize_legacy_stream_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            voices_dir = Path(tmp)
            (voices_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake")
            provider = PiperVoiceProvider(
                VoiceSettings(voice_id="en_US-lessac-medium"),
                voices_dir=voices_dir,
            )
            with _install_fake_piper(_LegacyFakePiperVoice):
                response = provider.synthesize(
                    VoiceSynthesisRequest(
                        text="Legacy path.",
                        voice_id="en_US-lessac-medium",
                    )
                )
            self.assertTrue(response.audio_bytes.startswith(b"RIFF"))


class PiperRegistryTests(unittest.TestCase):
    def test_registry_builds_piper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "voices" / "piper").mkdir(parents=True)
            config = AppConfig(data_root=root, project_root=root / "yt")
            config.voice_provider = PIPER_PROVIDER_ID
            provider = VoiceProviderRegistry(config).require_voice_provider(
                provider_id=PIPER_PROVIDER_ID
            )
            self.assertIsInstance(provider, PiperVoiceProvider)
            self.assertEqual(provider.provider_id, PIPER_PROVIDER_ID)
            self.assertEqual(
                provider.voices_dir,
                (root / "voices" / "piper").resolve(),
            )

    def test_discovery_lists_piper_voices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            piper_dir = root / "voices" / "piper"
            piper_dir.mkdir(parents=True)
            (piper_dir / "en_US-amy-low.onnx").write_bytes(b"fake")
            config = AppConfig(data_root=root, project_root=root / "yt")
            service = VoiceDiscoveryService(config)
            with _install_fake_piper():
                result = service.discover(provider_id=PIPER_PROVIDER_ID)
            self.assertTrue(result.ok)
            self.assertEqual(len(result.voices), 1)
            self.assertEqual(result.voices[0].voice_id, "en_US-amy-low")


if __name__ == "__main__":
    unittest.main()
