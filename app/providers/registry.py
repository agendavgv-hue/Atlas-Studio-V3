"""Resolve configured text providers for ProductionEngine."""

from __future__ import annotations

import os

from app.ai.factory import create_text_provider
from app.ai.settings import AIOrchestratorSettings
from app.core.app_config import AppConfig
from app.providers.base import TextProvider
from app.providers.errors import ProviderConfigurationError


class ProviderRegistry:
    """Creates real providers from app configuration. Never returns test doubles."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def require_text_provider(self) -> TextProvider:
        """Default text provider (legacy single-provider path)."""
        provider_id = (self._config.text_provider or "").strip().casefold()
        if not provider_id:
            if self._gemini_api_key():
                provider_id = "gemini"
            else:
                # Prefer Orchestrator default_text binding when present.
                ai = getattr(self._config, "ai", None) or AIOrchestratorSettings.defaults()
                binding = ai.binding_for("default_text")
                provider_id = (binding.provider or "").strip().casefold() or "ollama"

        try:
            ai = getattr(self._config, "ai", None)
            model = ""
            if provider_id == "gemini":
                model = (self._config.gemini_model or "").strip()
            elif ai is not None:
                model = ai.binding_for("default_text").model
            return create_text_provider(
                provider_id,
                config=self._config,
                model=model,
                ai_settings=ai,
            )
        except ProviderConfigurationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderConfigurationError(str(exc)) from exc

    def _gemini_api_key(self) -> str:
        configured = (self._config.gemini_api_key or "").strip()
        if configured:
            return configured
        return (
            os.environ.get("ATLAS_GEMINI_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
        )
