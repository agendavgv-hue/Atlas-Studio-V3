"""AI Orchestrator — decides which provider/model serves each Atlas role."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.ai.factory import create_image_provider, create_text_provider
from app.ai.roles import AIRole, ROLE_LABELS
from app.ai.settings import AIOrchestratorSettings, RoleBinding
from app.providers.base import TextProvider
from app.providers.errors import ProviderConfigurationError, ProviderError
from app.providers.image_base import ImageProvider

if TYPE_CHECKING:
    from app.core.app_config import AppConfig


@dataclass(frozen=True)
class ResolvedAI:
    role: AIRole
    provider_id: str
    model: str
    provider: TextProvider | ImageProvider
    used_fallback: bool = False


class AIOrchestratorService:
    """Single entry for role → AI resolution. Pipelines never pick vendors."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._ai = getattr(config, "ai", None) or AIOrchestratorSettings.defaults()

    @property
    def settings(self) -> AIOrchestratorSettings:
        return self._ai

    def resolve_text(self, role: AIRole | str) -> ResolvedAI:
        role_enum = role if isinstance(role, AIRole) else AIRole(str(role))
        binding = self._ai.binding_for(role_enum)
        try:
            provider = create_text_provider(
                binding.provider or "gemini",
                config=self._config,
                model=binding.model,
                ai_settings=self._ai,
            )
            return ResolvedAI(
                role=role_enum,
                provider_id=provider.provider_id,
                model=binding.model or getattr(provider, "model", "") or "",
                provider=provider,
                used_fallback=False,
            )
        except (ProviderConfigurationError, ProviderError, ValueError) as primary_exc:
            if not binding.fallback_provider:
                raise ProviderConfigurationError(
                    f"{ROLE_LABELS.get(role_enum, role_enum.value)} AI unavailable: {primary_exc}"
                ) from primary_exc
            provider = create_text_provider(
                binding.fallback_provider,
                config=self._config,
                model=binding.fallback_model,
                ai_settings=self._ai,
            )
            return ResolvedAI(
                role=role_enum,
                provider_id=provider.provider_id,
                model=binding.fallback_model or getattr(provider, "model", "") or "",
                provider=provider,
                used_fallback=True,
            )

    def text_for(self, role: AIRole | str) -> TextProvider:
        resolved = self.resolve_text(role)
        assert isinstance(resolved.provider, TextProvider)
        return resolved.provider

    def resolve_image(self, role: AIRole | str = AIRole.IMAGE_GENERATOR) -> ResolvedAI:
        role_enum = role if isinstance(role, AIRole) else AIRole(str(role))
        binding = self._ai.binding_for(role_enum)
        provider_id = binding.provider or self._config.image_provider or "forge"
        provider = create_image_provider(provider_id, config=self._config)
        return ResolvedAI(
            role=role_enum,
            provider_id=provider.provider_id,
            model=binding.model,
            provider=provider,
            used_fallback=False,
        )

    def image_for(self, role: AIRole | str = AIRole.IMAGE_GENERATOR) -> ImageProvider:
        resolved = self.resolve_image(role)
        assert isinstance(resolved.provider, ImageProvider)
        return resolved.provider

    def describe_routing(self) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for role in AIRole:
            binding = self._ai.binding_for(role)
            out[role.value] = binding.to_dict()
        return out


def try_text_with_fallback(
    orchestrator: AIOrchestratorService,
    role: AIRole,
    prompt: str,
    *,
    system: str | None = None,
) -> tuple[str, ResolvedAI]:
    """Generate text; if primary fails at runtime, attempt fallback binding."""
    resolved = orchestrator.resolve_text(role)
    provider = resolved.provider
    assert isinstance(provider, TextProvider)
    try:
        return provider.generate_text(prompt, system=system), resolved
    except ProviderError:
        binding = orchestrator.settings.binding_for(role)
        if not binding.fallback_provider or resolved.used_fallback:
            raise
        # Force fallback path
        forced = RoleBinding(
            provider=binding.fallback_provider,
            model=binding.fallback_model,
        )
        provider = create_text_provider(
            forced.provider,
            config=orchestrator._config,  # noqa: SLF001
            model=forced.model,
            ai_settings=orchestrator.settings,
        )
        text = provider.generate_text(prompt, system=system)
        return text, ResolvedAI(
            role=role,
            provider_id=provider.provider_id,
            model=forced.model,
            provider=provider,
            used_fallback=True,
        )
