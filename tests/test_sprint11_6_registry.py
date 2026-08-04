"""Registry + compatibility tests for Kokoro as default voice provider."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.app_config import AppConfig
from app.providers.errors import ProviderConfigurationError, ProviderError
from app.providers.kokoro import KOKORO_PROVIDER_ID, KokoroProvider
from app.providers.local_voice import LOCAL_VOICE_PROVIDER_ID
from app.providers.voice_registry import VoiceProviderRegistry


class VoiceRegistryKokoroTests(unittest.TestCase):
    def test_default_provider_is_kokoro(self) -> None:
        config = AppConfig(data_root=Path("."))
        config.voice_provider = None
        provider = VoiceProviderRegistry(config).require_voice_provider()
        self.assertIsInstance(provider, KokoroProvider)
        self.assertEqual(provider.provider_id, KOKORO_PROVIDER_ID)

    def test_local_alias_resolves_to_kokoro(self) -> None:
        config = AppConfig(data_root=Path("."))
        config.voice_provider = LOCAL_VOICE_PROVIDER_ID
        provider = VoiceProviderRegistry(config).require_voice_provider()
        self.assertIsInstance(provider, KokoroProvider)
        self.assertEqual(provider.provider_id, KOKORO_PROVIDER_ID)

    def test_explicit_kokoro_id(self) -> None:
        config = AppConfig(data_root=Path("."))
        config.voice_provider = "kokoro"
        provider = VoiceProviderRegistry(config).require_voice_provider()
        self.assertIsInstance(provider, KokoroProvider)

    def test_kokoro_model_dir_uses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(data_root=root)
            config.voice_provider = "kokoro"
            provider = VoiceProviderRegistry(config).require_voice_provider()
            assert isinstance(provider, KokoroProvider)
            self.assertEqual(provider.model_dir, (root / "Cache" / "kokoro").resolve())

    def test_elevenlabs_still_supported(self) -> None:
        config = AppConfig(data_root=Path("."))
        config.voice_provider = "elevenlabs"
        config.voice.api_key = "sk-test"
        provider = VoiceProviderRegistry(config).require_voice_provider()
        self.assertEqual(provider.provider_id, "elevenlabs")

    def test_elevenlabs_requires_api_key(self) -> None:
        config = AppConfig(data_root=Path("."))
        config.voice_provider = "elevenlabs"
        config.voice.api_key = ""
        with self.assertRaises(ProviderConfigurationError):
            VoiceProviderRegistry(config).require_voice_provider()

    def test_pipeline_generate_uses_registry_kokoro_without_pipeline_changes(self) -> None:
        """Generator/Service stay agnostic — only registry returns Kokoro."""
        import app.voice.generator as gen_mod
        import app.voice.service as svc_mod

        gen_text = Path(gen_mod.__file__).read_text(encoding="utf-8")
        svc_text = Path(svc_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("kokoro", gen_text.casefold())
        self.assertNotIn("kokoro", svc_text.casefold())
        self.assertNotIn("piper", gen_text.casefold())
        self.assertNotIn("piper", svc_text.casefold())
        self.assertNotIn("KokoroProvider", gen_text)
        self.assertNotIn("KokoroProvider", svc_text)
        self.assertNotIn("PiperVoiceProvider", gen_text)
        self.assertNotIn("PiperVoiceProvider", svc_text)

    def test_explicit_piper_id(self) -> None:
        from app.providers.piper import PiperVoiceProvider

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "voices" / "piper").mkdir(parents=True)
            config = AppConfig(data_root=root)
            provider = VoiceProviderRegistry(config).require_voice_provider(
                provider_id="piper"
            )
            self.assertIsInstance(provider, PiperVoiceProvider)
            self.assertEqual(provider.provider_id, "piper")

    def test_missing_kokoro_runtime_fails_cleanly(self) -> None:
        config = AppConfig(data_root=Path("."))
        config.voice_provider = None
        provider = VoiceProviderRegistry(config).require_voice_provider()
        with patch.object(
            KokoroProvider,
            "_ensure_runtime",
            side_effect=ProviderError("Kokoro is not installed"),
        ):
            with self.assertRaises(ProviderError) as raised:
                provider.validate_ready()
            self.assertIn("Kokoro", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
