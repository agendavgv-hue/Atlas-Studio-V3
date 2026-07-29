"""Resolve configured voice providers for ProductionEngine."""

from __future__ import annotations

from app.core.app_config import AppConfig
from app.providers.elevenlabs import ElevenLabsVoiceProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.local_voice import LOCAL_VOICE_PROVIDER_ID, LocalVoiceProvider
from app.providers.voice_base import VoiceProvider


class VoiceProviderRegistry:
    """Creates real voice providers from app configuration. No production fakes."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def require_voice_provider(self) -> VoiceProvider:
        provider_id = (self._config.voice_provider or "").strip().casefold()
        if not provider_id:
            # Free-first: Local Voice Engine is always the default.
            provider_id = LOCAL_VOICE_PROVIDER_ID

        if provider_id in {LOCAL_VOICE_PROVIDER_ID, "kokoro"}:
            # "kokoro" accepted only as a legacy alias — never shown in UI.
            return LocalVoiceProvider(self._config.voice)

        if provider_id == "elevenlabs":
            settings = self._config.voice
            if not settings.api_key.strip():
                raise ProviderConfigurationError(
                    "ElevenLabs API key is empty. "
                    "Configure Voice Provider settings, or switch to Local Voice Engine."
                )
            return ElevenLabsVoiceProvider(settings)

        raise ProviderConfigurationError(
            f"Unsupported voice provider '{provider_id}'. "
            "Supported: local (Local Voice Engine), elevenlabs (optional)."
        )
