"""Text provider protocol used by production pipelines."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TextProvider(ABC):
    """Generates plain text for scripts, sheets, SEO, etc."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable id (e.g. ``gemini``)."""

    @abstractmethod
    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        """Return model text. Raises ``ProviderError`` on failure."""
