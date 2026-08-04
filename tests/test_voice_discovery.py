"""VoiceDiscoveryService — single source of truth for TTS catalogues."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.app_config import AppConfig
from app.core.voice_settings import VoiceSettings
from app.providers.errors import ProviderConfigurationError, ProviderError
from app.providers.voice_base import VoiceInfo
from app.providers.voice_discovery import VoiceDiscoveryResult, VoiceDiscoveryService
from app.providers.voice_registry import KOKORO_PROVIDER_ID


class VoiceDiscoveryResultTests(unittest.TestCase):
    def test_empty_message_prefers_error(self) -> None:
        result = VoiceDiscoveryResult(
            provider_id="kokoro",
            model_dir="/tmp/kokoro",
            error="Missing voices-v1.0.bin",
        )
        self.assertFalse(result.ok)
        self.assertIn("Missing voices-v1.0.bin", result.empty_message)


class VoiceDiscoveryServiceTests(unittest.TestCase):
    def test_kokoro_model_dir_matches_generation_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(data_root=root / "data", project_root=root / "yt")
            service = VoiceDiscoveryService(config)
            expected = root / "data" / "Cache" / "kokoro"
            # StoragePaths may use cache/ lowercase — compare via service.
            self.assertEqual(service.kokoro_model_dir(), service.kokoro_model_dir())
            self.assertTrue(str(service.kokoro_model_dir()).endswith("kokoro"))

    def test_discover_surfaces_provider_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(data_root=root / "data", project_root=root / "yt")
            service = VoiceDiscoveryService(config)
            result = service.discover(
                provider_id="elevenlabs",
                settings=VoiceSettings(api_key=""),
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.voices, [])
            self.assertIn("API key", result.empty_message)

    def test_discover_returns_provider_voices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(data_root=root / "data", project_root=root / "yt")
            service = VoiceDiscoveryService(config)
            fake_provider = MagicMock()
            fake_provider.provider_id = KOKORO_PROVIDER_ID
            fake_provider.model_dir = root / "data" / "Cache" / "kokoro"
            fake_provider.list_voices.return_value = [
                VoiceInfo("af_heart", "Heart", "en-US", gender="Female"),
                VoiceInfo("am_adam", "Adam", "en-US", gender="Male"),
            ]
            with patch.object(service, "resolve_provider", return_value=fake_provider):
                result = service.discover(provider_id=KOKORO_PROVIDER_ID)
            self.assertTrue(result.ok)
            self.assertEqual(len(result.voices), 2)
            self.assertEqual(result.voices[0].voice_id, "af_heart")

    def test_discover_surfaces_list_voices_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(data_root=root / "data", project_root=root / "yt")
            service = VoiceDiscoveryService(config)
            fake_provider = MagicMock()
            fake_provider.provider_id = KOKORO_PROVIDER_ID
            fake_provider.model_dir = root / "missing"
            fake_provider.list_voices.side_effect = ProviderError(
                "Kokoro model files are missing: voices-v1.0.bin. "
                f"Place them in {root / 'missing'}."
            )
            with patch.object(service, "resolve_provider", return_value=fake_provider):
                result = service.discover(provider_id=KOKORO_PROVIDER_ID)
            self.assertFalse(result.ok)
            self.assertIn("voices-v1.0.bin", result.empty_message)

    def test_language_filter_falls_back_to_all_voices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(data_root=root / "data", project_root=root / "yt")
            service = VoiceDiscoveryService(config)
            fake_provider = MagicMock()
            fake_provider.provider_id = KOKORO_PROVIDER_ID
            fake_provider.model_dir = root / "kokoro"
            fake_provider.list_voices.return_value = [
                VoiceInfo("af_heart", "Heart", "en-US", gender="Female"),
            ]
            with patch.object(service, "resolve_provider", return_value=fake_provider):
                result = service.discover(
                    provider_id=KOKORO_PROVIDER_ID,
                    channel_language="nl",
                )
            self.assertTrue(result.ok)
            self.assertEqual(len(result.voices), 1)
            self.assertIn("none match", result.warning.casefold())


if __name__ == "__main__":
    unittest.main()
