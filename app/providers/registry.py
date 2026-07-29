"""Resolve configured text providers for ProductionEngine."""

from __future__ import annotations

import os

from app.core.app_config import AppConfig
from app.providers.base import TextProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.gemini import GeminiTextProvider


class ProviderRegistry:
    """Creates real providers from app configuration. Never returns test doubles."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def require_text_provider(self) -> TextProvider:
        provider_id = (self._config.text_provider or "").strip().casefold()
        if not provider_id:
            # Sensible default when a Gemini key exists.
            if self._gemini_api_key():
                provider_id = "gemini"
            else:
                raise ProviderConfigurationError(
                    "No AI text provider is configured. "
                    "Open Settings, choose a provider, and enter an API key."
                )

        if provider_id == "gemini":
            key = self._gemini_api_key()
            if not key:
                raise ProviderConfigurationError(
                    "Gemini is selected but no API key is set. "
                    "Add your Gemini API key in Settings."
                )
            model = (self._config.gemini_model or "").strip()
            if not model:
                raise ProviderConfigurationError(
                    "No Gemini model is selected. "
                    "Open Settings, click Test Connection, choose a model, and save."
                )
            return GeminiTextProvider(key, model=model)

        raise ProviderConfigurationError(
            f"Unsupported text provider '{provider_id}'. "
            "Supported providers: gemini."
        )

    def _gemini_api_key(self) -> str:
        configured = (self._config.gemini_api_key or "").strip()
        if configured:
            return configured
        return (
            os.environ.get("ATLAS_GEMINI_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
        )
