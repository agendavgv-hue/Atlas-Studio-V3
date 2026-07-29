"""Resolve configured image providers for ProductionEngine."""

from __future__ import annotations

from app.core.app_config import AppConfig
from app.providers.errors import ProviderConfigurationError
from app.providers.forge import ForgeImageProvider
from app.providers.image_base import ImageProvider


class ImageProviderRegistry:
    """Creates real image providers from app configuration. No production fakes."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def require_image_provider(self) -> ImageProvider:
        provider_id = (self._config.image_provider or "").strip().casefold()
        if not provider_id:
            if self._config.forge.host.strip():
                provider_id = "forge"
            else:
                raise ProviderConfigurationError(
                    "No image provider is configured. "
                    "Open Settings, choose Forge, and save Image Provider settings."
                )

        if provider_id == "forge":
            settings = self._config.forge
            if not settings.host.strip():
                raise ProviderConfigurationError(
                    "Forge host is empty. Configure Image Provider settings."
                )
            return ForgeImageProvider(settings)

        raise ProviderConfigurationError(
            f"Unsupported image provider '{provider_id}'. Supported: forge."
        )
