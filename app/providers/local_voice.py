"""Local Voice Engine — legacy provider id retained for compatibility.

Sprint 11+: Kokoro is the default local VoiceProvider
(``app.providers.kokoro.KokoroProvider``). Configurations that still store
``voice_provider = "local"`` are resolved to Kokoro by VoiceProviderRegistry.

This module keeps the historical constants and a thin unavailable stub for
older tests/docs that reference Local Voice Engine by name.
"""

from __future__ import annotations

from app.core.voice_settings import VoiceSettings
from app.providers.errors import ProviderError
from app.providers.voice_base import (
    VoiceInfo,
    VoiceProvider,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)

# Legacy id — registry aliases this to KokoroProvider.
LOCAL_VOICE_PROVIDER_ID = "local"
LOCAL_VOICE_PROVIDER_LABEL = "Local Voice Engine (Legacy)"

LOCAL_VOICE_UNAVAILABLE_MESSAGE = (
    "Local Voice Engine id is legacy. "
    "Atlas Studio now uses Kokoro ONNX as the default local provider. "
    "Select Kokoro in Settings, or install dependencies with: "
    "pip install -r requirements-voice-local.txt"
)


class LocalVoiceProvider(VoiceProvider):
    """Deprecated stub. Prefer ``KokoroProvider`` via the registry."""

    def __init__(self, settings: VoiceSettings) -> None:
        self._settings = settings

    @property
    def provider_id(self) -> str:
        return LOCAL_VOICE_PROVIDER_ID

    @property
    def settings(self) -> VoiceSettings:
        return self._settings

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        raise ProviderError(LOCAL_VOICE_UNAVAILABLE_MESSAGE)

    def list_voices(self) -> list[VoiceInfo]:
        raise ProviderError(LOCAL_VOICE_UNAVAILABLE_MESSAGE)

    def list_models(self) -> list[str]:
        return []

    def test_connection(self) -> str:
        raise ProviderError(LOCAL_VOICE_UNAVAILABLE_MESSAGE)

    def validate_ready(self) -> None:
        raise ProviderError(LOCAL_VOICE_UNAVAILABLE_MESSAGE)
