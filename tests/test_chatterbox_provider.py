"""ChatterboxVoiceProvider — package discovery + optional reference clips."""

from __future__ import annotations

import io
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.core.app_config import AppConfig
from app.core.voice_settings import VoiceSettings
from app.providers.chatterbox import (
    CHATTERBOX_PROVIDER_ID,
    ChatterboxVoiceProvider,
    ensure_chatterbox_voices_dir,
)
from app.providers.errors import ProviderError
from app.providers.voice_base import VoiceSynthesisRequest
from app.providers.voice_discovery import VoiceDiscoveryService
from app.providers.voice_registry import VoiceProviderRegistry
from app.voice.generator import synthesize_with_provider


class _FakeEnglishTTS:
    sr = 24000

    @classmethod
    def from_pretrained(cls, device="cpu", **_kwargs):
        del device
        return cls()

    @classmethod
    def from_local(cls, ckpt_dir, device="cpu"):
        del ckpt_dir, device
        return cls()

    def generate(self, text, audio_prompt_path=None, **_kwargs):
        del text, audio_prompt_path, _kwargs
        return np.zeros(800, dtype=np.float32)


class _FakeMultilingualTTS:
    sr = 24000

    @classmethod
    def get_supported_languages(cls):
        return {"en": "English", "nl": "Dutch", "fr": "French"}

    @classmethod
    def from_pretrained(cls, device="cpu", **_kwargs):
        del device, _kwargs
        return cls()

    def generate(self, text, language_id=None, audio_prompt_path=None, **_kwargs):
        del text, language_id, audio_prompt_path, _kwargs
        return np.zeros(1200, dtype=np.float32)


def _install_fake_chatterbox(*, english=True, multilingual=True, turbo=False):
    """Install a minimal chatterbox package into sys.modules."""
    package = types.ModuleType("chatterbox")
    package.__path__ = []  # type: ignore[attr-defined]

    modules: dict[str, types.ModuleType] = {"chatterbox": package}

    if english:
        tts_mod = types.ModuleType("chatterbox.tts")
        tts_mod.ChatterboxTTS = _FakeEnglishTTS  # type: ignore[attr-defined]
        modules["chatterbox.tts"] = tts_mod
        package.tts = tts_mod  # type: ignore[attr-defined]

    if multilingual:
        mtl_mod = types.ModuleType("chatterbox.mtl_tts")
        mtl_mod.ChatterboxMultilingualTTS = _FakeMultilingualTTS  # type: ignore[attr-defined]
        mtl_mod.SUPPORTED_LANGUAGES = _FakeMultilingualTTS.get_supported_languages()
        modules["chatterbox.mtl_tts"] = mtl_mod
        package.mtl_tts = mtl_mod  # type: ignore[attr-defined]

    if turbo:
        turbo_mod = types.ModuleType("chatterbox.tts_turbo")

        class _FakeTurbo:
            sr = 24000

            @classmethod
            def from_pretrained(cls, device="cpu", **_kwargs):
                del device, _kwargs
                return cls()

            def generate(self, text, audio_prompt_path=None, **_kwargs):
                del text, _kwargs
                if not audio_prompt_path:
                    raise ValueError("audio_prompt_path required")
                return np.zeros(400, dtype=np.float32)

        turbo_mod.ChatterboxTurboTTS = _FakeTurbo  # type: ignore[attr-defined]
        modules["chatterbox.tts_turbo"] = turbo_mod
        package.tts_turbo = turbo_mod  # type: ignore[attr-defined]

    return patch.dict(sys.modules, modules)


class ChatterboxHelperTests(unittest.TestCase):
    def test_ensure_voices_dir_creates_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = ensure_chatterbox_voices_dir(root)
            self.assertTrue(path.is_dir())
            self.assertEqual(path, (root / "voices" / "chatterbox").resolve())


class ChatterboxProviderTests(unittest.TestCase):
    def test_list_voices_uses_official_language_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            voices_dir = Path(tmp)
            provider = ChatterboxVoiceProvider(VoiceSettings(), voices_dir=voices_dir)
            with _install_fake_chatterbox():
                voices = provider.list_voices()
            ids = {v.voice_id for v in voices}
            self.assertIn("default", ids)
            self.assertIn("lang:nl", ids)
            self.assertIn("lang:fr", ids)
            self.assertNotIn("lang:en", ids)  # covered by default

    def test_list_voices_includes_reference_clips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            voices_dir = Path(tmp)
            (voices_dir / "storyteller.wav").write_bytes(b"RIFF")
            provider = ChatterboxVoiceProvider(VoiceSettings(), voices_dir=voices_dir)
            with _install_fake_chatterbox():
                voices = provider.list_voices()
            ids = {v.voice_id for v in voices}
            self.assertIn("ref:storyteller", ids)

    def test_synthesize_returns_wav(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            voices_dir = Path(tmp) / "voices"
            voices_dir.mkdir()
            models_root = Path(tmp) / "AI" / "Models"
            from app.core.ai_storage import ensure_ai_models_layout
            from app.providers.chatterbox_install import CHATTERBOX_ENGLISH_FILES

            ensure_ai_models_layout(models_root)
            local = models_root / "Chatterbox"
            for name in CHATTERBOX_ENGLISH_FILES:
                (local / name).write_bytes(b"x")

            provider = ChatterboxVoiceProvider(
                VoiceSettings(voice_id="default", language="en-US"),
                voices_dir=voices_dir,
            )
            with _install_fake_chatterbox():
                with patch(
                    "app.providers.chatterbox_install.is_chatterbox_english_installed",
                    return_value=True,
                ), patch(
                    "app.providers.chatterbox_install.require_chatterbox_english",
                    return_value=local.resolve(),
                ), patch(
                    "app.core.ai_storage.apply_ai_storage_environment",
                    return_value=models_root.resolve(),
                ):
                    response = synthesize_with_provider(
                        provider,
                        VoiceSynthesisRequest(
                            text="Hello from Chatterbox.",
                            voice_id="default",
                            language="en-US",
                        ),
                    )
            self.assertEqual(response.voice_id, "default")
            self.assertTrue(response.audio_bytes.startswith(b"RIFF"))
            self.assertEqual(response.content_type, "audio/wav")
            with wave.open(io.BytesIO(response.audio_bytes), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 1)

    def test_missing_package_raises_concrete_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = ChatterboxVoiceProvider(VoiceSettings(), voices_dir=Path(tmp))
            with patch.dict(sys.modules, {"chatterbox": None}):
                with self.assertRaises(ProviderError) as ctx:
                    provider.validate_ready()
            self.assertIn("chatterbox-tts", str(ctx.exception).casefold())

    def test_reference_voice_required_path_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = ChatterboxVoiceProvider(
                VoiceSettings(
                    voice_id="default",
                    reference_audio_path=str(Path(tmp) / "missing.wav"),
                ),
                voices_dir=Path(tmp),
            )
            with _install_fake_chatterbox():
                with self.assertRaises(ProviderError) as ctx:
                    provider.synthesize(
                        VoiceSynthesisRequest(text="Hello", voice_id="default")
                    )
            self.assertIn("reference voice", str(ctx.exception).casefold())


class ChatterboxRegistryTests(unittest.TestCase):
    def test_registry_builds_chatterbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "voices" / "chatterbox").mkdir(parents=True)
            config = AppConfig(data_root=root, project_root=root / "yt")
            config.voice_provider = CHATTERBOX_PROVIDER_ID
            provider = VoiceProviderRegistry(config).require_voice_provider(
                provider_id=CHATTERBOX_PROVIDER_ID
            )
            self.assertIsInstance(provider, ChatterboxVoiceProvider)
            self.assertEqual(
                provider.voices_dir,
                (root / "voices" / "chatterbox").resolve(),
            )

    def test_discovery_lists_chatterbox_voices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chatter_dir = root / "voices" / "chatterbox"
            chatter_dir.mkdir(parents=True)
            (chatter_dir / "hero.wav").write_bytes(b"RIFF")
            config = AppConfig(data_root=root, project_root=root / "yt")
            service = VoiceDiscoveryService(config)
            with _install_fake_chatterbox():
                result = service.discover(provider_id=CHATTERBOX_PROVIDER_ID)
            self.assertTrue(result.ok)
            ids = {v.voice_id for v in result.voices}
            self.assertIn("default", ids)
            self.assertIn("ref:hero", ids)


if __name__ == "__main__":
    unittest.main()
