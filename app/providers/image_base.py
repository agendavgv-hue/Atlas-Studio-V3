"""Image provider protocol — Forge, ComfyUI, and future backends share this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ImageGenerationRequest:
    """Provider-ready image request. Resolution comes from provider settings."""

    prompt: str
    negative_prompt: str = ""
    width: int = 0
    height: int = 0
    steps: int = 0
    cfg_scale: float = 0.0
    sampler: str = ""
    scheduler: str = ""
    seed: int = -1
    model: str = ""


@dataclass(frozen=True)
class ImageGenerationResponse:
    image_png: bytes
    seed: int
    model: str = ""
    sampler: str = ""
    steps: int = 0
    cfg_scale: float = 0.0
    width: int = 0
    height: int = 0
    generation_time_ms: float = 0.0


class ImageProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable id (e.g. ``forge``)."""

    @abstractmethod
    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """Return PNG bytes. Raises ``ProviderError`` on failure."""

    @abstractmethod
    def list_models(self) -> list[str]:
        """Models available on the backend."""

    @abstractmethod
    def test_connection(self) -> str:
        """Soft check for Settings UI. May succeed without a selected model."""

    def validate_ready(self) -> None:
        """Hard check before generation. Raises ``ProviderError`` if not ready."""
        self.test_connection()
