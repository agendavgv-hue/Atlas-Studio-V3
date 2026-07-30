"""Voice provider protocol — Kokoro and optional cloud backends share this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceInfo:
    """Selectable voice from a provider catalogue.

    Future providers (Kokoro, ElevenLabs, OpenAI, Google, Azure, Piper, …)
    should fill as many of these fields as the backend exposes. The Voice
    Library UI is built against this shape only — never against vendor ids.
    """

    voice_id: str
    name: str
    language: str = ""
    description: str = ""
    gender: str = ""
    accent: str = ""
    age: str = ""
    style_tags: tuple[str, ...] = ()
    sample_text: str = ""


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
        """Stable id (e.g. ``kokoro``, ``elevenlabs``)."""

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
