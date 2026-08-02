"""Build concrete TextProvider / ImageProvider instances from config."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.providers.base import TextProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.gemini import GeminiTextProvider
from app.providers.image_base import ImageProvider
from app.providers.ollama import OllamaTextProvider
from app.providers.openai_compat import AnthropicTextProvider, OpenAICompatTextProvider

if TYPE_CHECKING:
    from app.core.app_config import AppConfig
    from app.ai.settings import AIOrchestratorSettings


# Alias providers that resolve to Ollama with a preferred model family.
_OLLAMA_ALIASES: dict[str, str] = {
    "qwen": "qwen2.5:14b",
    "gemma": "gemma2:9b",
    "deepseek-local": "deepseek-r1:14b",
}


def create_text_provider(
    provider_id: str,
    *,
    config: AppConfig,
    model: str = "",
    ai_settings: AIOrchestratorSettings | None = None,
) -> TextProvider:
    """Instantiate a text provider. Generators must not call this — use Orchestrator."""
    from app.ai.settings import AIOrchestratorSettings as SettingsCls

    ai = ai_settings or getattr(config, "ai", None) or SettingsCls.defaults()
    pid = (provider_id or "").strip().casefold()
    model_name = (model or "").strip()

    if pid in _OLLAMA_ALIASES or pid == "ollama":
        preferred = model_name or (
            _OLLAMA_ALIASES.get(pid) if pid in _OLLAMA_ALIASES else "qwen2.5:14b"
        )
        return OllamaTextProvider(host=ai.ollama_host, model=preferred)

    if pid == "gemini":
        key = _gemini_key(config)
        if not key:
            raise ProviderConfigurationError("Gemini API key is missing.")
        resolved = model_name or (config.gemini_model or "").strip()
        if not resolved:
            raise ProviderConfigurationError("Gemini model is not selected.")
        return GeminiTextProvider(key, model=resolved)

    if pid == "openai":
        key = ai.openai_api_key or os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise ProviderConfigurationError("OpenAI API key is missing.")
        if not model_name:
            model_name = "gpt-4o-mini"
        return OpenAICompatTextProvider(
            api_key=key,
            model=model_name,
            base_url=ai.openai_base_url,
            provider_id="openai",
        )

    if pid == "deepseek":
        key = ai.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not key:
            raise ProviderConfigurationError("DeepSeek API key is missing.")
        if not model_name:
            model_name = "deepseek-chat"
        return OpenAICompatTextProvider(
            api_key=key,
            model=model_name,
            base_url=ai.deepseek_base_url,
            provider_id="deepseek",
        )

    if pid == "anthropic" or pid == "claude":
        key = ai.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise ProviderConfigurationError("Anthropic API key is missing.")
        if not model_name:
            model_name = "claude-sonnet-4-20250514"
        return AnthropicTextProvider(api_key=key, model=model_name)

    raise ProviderConfigurationError(
        f"Unsupported text provider '{provider_id}'. "
        "Supported: ollama, qwen, gemma, gemini, openai, anthropic, deepseek."
    )


def create_image_provider(
    provider_id: str,
    *,
    config: AppConfig,
) -> ImageProvider:
    from app.providers.forge import ForgeImageProvider

    pid = (provider_id or "forge").strip().casefold() or "forge"
    if pid != "forge":
        raise ProviderConfigurationError(
            f"Unsupported image provider '{provider_id}'. Supported: forge."
        )
    return ForgeImageProvider(config.forge)


def _gemini_key(config: AppConfig) -> str:
    configured = (config.gemini_api_key or "").strip()
    if configured:
        return configured
    return (
        os.environ.get("ATLAS_GEMINI_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )
