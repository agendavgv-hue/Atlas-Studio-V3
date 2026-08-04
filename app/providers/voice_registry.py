"""Resolve configured voice providers for ProductionEngine."""

from __future__ import annotations

from app.core.app_config import AppConfig
from app.core.storage_paths import StoragePaths
from app.core.voice_settings import VoiceSettings
from app.providers.errors import ProviderConfigurationError
from app.providers.voice_base import VoiceProvider

# Keep ids here so importing this registry does not load provider SDKs.
KOKORO_PROVIDER_ID = "kokoro"
CHATTERBOX_PROVIDER_ID = "chatterbox"
LOCAL_VOICE_PROVIDER_ID = "local"


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

        # Piper was replaced by Chatterbox — fail with an actionable message.
        if resolved_id == "piper":
            raise ProviderConfigurationError(
                "Piper has been removed. Select Chatterbox as the second local "
                "voice provider in Voice Settings / Channel Settings."
            )

        voice_settings = settings if settings is not None else self._config.voice

        if resolved_id in {KOKORO_PROVIDER_ID, LOCAL_VOICE_PROVIDER_ID}:
            from app.providers.kokoro import KokoroProvider

            # ``local`` remains a backward-compatible alias for Kokoro.
            model_dir = StoragePaths(self._config.data_root).cache / "kokoro"
            return KokoroProvider(voice_settings, model_dir=model_dir)

        if resolved_id == CHATTERBOX_PROVIDER_ID:
            from app.providers.chatterbox import (
                ChatterboxVoiceProvider,
                ensure_chatterbox_voices_dir,
            )

            return ChatterboxVoiceProvider(
                voice_settings,
                voices_dir=ensure_chatterbox_voices_dir(self._config.data_root),
            )

        if resolved_id == "elevenlabs":
            from app.providers.elevenlabs import ElevenLabsVoiceProvider

            if not voice_settings.api_key.strip():
                raise ProviderConfigurationError(
                    "ElevenLabs API key is empty. "
                    "Configure Voice Provider settings, or switch to Kokoro / Chatterbox."
                )
            return ElevenLabsVoiceProvider(voice_settings)

        raise ProviderConfigurationError(
            f"Unsupported voice provider '{resolved_id}'. "
            "Supported: kokoro (default), chatterbox (local), elevenlabs (optional)."
        )
