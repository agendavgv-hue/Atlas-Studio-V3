"""Voice provider protocol — Local Voice Engine and optional cloud backends share this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceInfo:
    """Selectable voice from a provider catalogue."""

    voice_id: str
    name: str
    language: str = ""
    description: str = ""


@dataclass(frozen=True)
class VoiceSynthesisRequest:
    """Provider-ready speech request. Voice knobs come from provider settings."""

    text: str
    voice_id: str = ""
    language: str = ""
    model: str = ""
    stability: float = 0.0
    style: float = 0.0
    speed: float = 0.0
    similarity: float = 0.0
    output_format: str = ""


@dataclass(frozen=True)
class VoiceSynthesisResponse:
    """Raw audio bytes plus generation metadata."""

    audio_bytes: bytes
    content_type: str = "audio/mpeg"
    model: str = ""
    voice_id: str = ""
    generation_time_ms: float = 0.0


class VoiceProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable id (e.g. ``local``, ``elevenlabs``)."""

    @abstractmethod
    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        """Return audio bytes. Raises ``ProviderError`` on failure."""

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        """Voices available on the backend."""

    @abstractmethod
    def list_models(self) -> list[str]:
        """Models available on the backend (may be empty if remote listing unsupported)."""

    @abstractmethod
    def test_connection(self) -> str:
        """Soft check for Settings UI. May succeed without a selected voice."""

    def validate_ready(self) -> None:
        """Hard check before generation. Raises ``ProviderError`` if not ready."""
        self.test_connection()
