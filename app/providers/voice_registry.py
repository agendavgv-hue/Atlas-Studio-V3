"""Resolve configured voice providers for ProductionEngine."""

from __future__ import annotations

from app.core.app_config import AppConfig
from app.core.storage_paths import StoragePaths
from app.core.voice_settings import VoiceSettings
from app.providers.elevenlabs import ElevenLabsVoiceProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.kokoro import KOKORO_PROVIDER_ID, KokoroProvider
from app.providers.local_voice import LOCAL_VOICE_PROVIDER_ID
from app.providers.voice_base import VoiceProvider


class VoiceProviderRegistry:
    """Creates real voice providers from app configuration. No production fakes."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def require_voice_provider(
        self,
        *,
        provider_id: str | None = None,
        settings: VoiceSettings | None = None,
    ) -> VoiceProvider:
        resolved_id = (provider_id or self._config.voice_provider or "").strip().casefold()
        if not resolved_id:
            # Free-first: Kokoro ONNX is the default local provider.
            resolved_id = KOKORO_PROVIDER_ID

        voice_settings = settings if settings is not None else self._config.voice

        if resolved_id in {KOKORO_PROVIDER_ID, LOCAL_VOICE_PROVIDER_ID}:
            # ``local`` remains a backward-compatible alias for Kokoro.
            model_dir = StoragePaths(self._config.data_root).cache / "kokoro"
            return KokoroProvider(voice_settings, model_dir=model_dir)

        if resolved_id == "elevenlabs":
            if not voice_settings.api_key.strip():
                raise ProviderConfigurationError(
                    "ElevenLabs API key is empty. "
                    "Configure Voice Provider settings, or switch to Kokoro."
                )
            return ElevenLabsVoiceProvider(voice_settings)

        raise ProviderConfigurationError(
            f"Unsupported voice provider '{resolved_id}'. "
            "Supported: kokoro (default), elevenlabs (optional)."
        )
