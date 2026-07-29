"""Local Voice Engine — free default TTS provider (architecture reserved).

Public identity is ``local`` (Local Voice Engine). The concrete synthesis
backend is an internal detail and may be replaced without UX changes.

Status (Sprint 7 pause):
    The previous candidate backend was not compatible with Atlas Studio's
    primary runtime (Python 3.13). Local synthesis is intentionally disabled
    until a Python 3.13–compatible engine is selected. Provider abstraction,
    registry, TaskManager, and Voice Pipeline interfaces remain intact.
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

# User-facing provider id — never expose a specific engine name in Settings.
LOCAL_VOICE_PROVIDER_ID = "local"
LOCAL_VOICE_PROVIDER_LABEL = "Local Voice Engine (Recommended)"

LOCAL_VOICE_UNAVAILABLE_MESSAGE = (
    "Local Voice Engine is temporarily unavailable. "
    "Atlas Studio targets Python 3.13; a compatible free local backend "
    "has not been selected yet. Voice generation will stay disabled until "
    "that backend is ready. Optional cloud providers remain available in Settings."
)

# Reserved catalogue — used once a Python 3.13–compatible backend ships.
_LOCAL_VOICES: tuple[VoiceInfo, ...] = (
    VoiceInfo("local_default", "Default", "en-US"),
)

_DEFAULT_VOICE_ID = "local_default"


class LocalVoiceProvider(VoiceProvider):
    """Default free voice provider slot. Synthesis postponed until backend ready."""

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
