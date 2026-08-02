"""Persisted AI Orchestrator settings — per-role provider + model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.ai.roles import AIRole


# Provider catalog (generic — no channel hardcoding).
TEXT_PROVIDER_IDS: tuple[str, ...] = (
    "ollama",
    "gemini",
    "openai",
    "anthropic",
    "deepseek",
    "qwen",  # alias → ollama + qwen model preference
    "gemma",  # alias → ollama + gemma model preference
)

IMAGE_PROVIDER_IDS: tuple[str, ...] = ("forge",)

DEFAULT_ROLE_BINDINGS: dict[str, dict[str, str]] = {
    AIRole.CREATIVE_DIRECTOR.value: {
        "provider": "ollama",
        "model": "qwen2.5:14b",
        "fallback_provider": "gemini",
        "fallback_model": "",
    },
    AIRole.IMAGE_GENERATOR.value: {
        "provider": "forge",
        "model": "",
        "fallback_provider": "",
        "fallback_model": "",
    },
    AIRole.CRITIC.value: {
        "provider": "ollama",
        "model": "qwen2.5:14b",
        "fallback_provider": "gemini",
        "fallback_model": "",
    },
    AIRole.SEO.value: {
        "provider": "ollama",
        "model": "gemma2:9b",
        "fallback_provider": "gemini",
        "fallback_model": "",
    },
    AIRole.STORY.value: {
        "provider": "ollama",
        "model": "qwen2.5:14b",
        "fallback_provider": "gemini",
        "fallback_model": "",
    },
    AIRole.DEFAULT_TEXT.value: {
        "provider": "gemini",
        "model": "",
        "fallback_provider": "ollama",
        "fallback_model": "qwen2.5:14b",
    },
}


@dataclass
class RoleBinding:
    provider: str = ""
    model: str = ""
    fallback_provider: str = ""
    fallback_model: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "model": self.model,
            "fallback_provider": self.fallback_provider,
            "fallback_model": self.fallback_model,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RoleBinding:
        raw = dict(data or {})
        return cls(
            provider=str(raw.get("provider") or "").strip(),
            model=str(raw.get("model") or "").strip(),
            fallback_provider=str(raw.get("fallback_provider") or "").strip(),
            fallback_model=str(raw.get("fallback_model") or "").strip(),
        )


@dataclass
class AIOrchestratorSettings:
    """Global AI routing for Atlas Studio."""

    ollama_host: str = "http://127.0.0.1:11434"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    roles: dict[str, RoleBinding] = field(default_factory=dict)

    def binding_for(self, role: AIRole | str) -> RoleBinding:
        key = role.value if isinstance(role, AIRole) else str(role)
        if key in self.roles:
            return self.roles[key]
        defaults = DEFAULT_ROLE_BINDINGS.get(key) or {}
        return RoleBinding.from_dict(defaults)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ollama_host": self.ollama_host,
            "openai_api_key": self.openai_api_key,
            "openai_base_url": self.openai_base_url,
            "anthropic_api_key": self.anthropic_api_key,
            "deepseek_api_key": self.deepseek_api_key,
            "deepseek_base_url": self.deepseek_base_url,
            "roles": {k: v.to_dict() for k, v in self.roles.items()},
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> AIOrchestratorSettings:
        raw = dict(data or {})
        roles_raw = raw.get("roles") if isinstance(raw.get("roles"), dict) else {}
        roles: dict[str, RoleBinding] = {}
        for key, default in DEFAULT_ROLE_BINDINGS.items():
            entry = roles_raw.get(key) if isinstance(roles_raw.get(key), dict) else default
            roles[key] = RoleBinding.from_dict(entry)
        # Preserve any extra custom roles.
        for key, value in roles_raw.items():
            if key not in roles and isinstance(value, dict):
                roles[str(key)] = RoleBinding.from_dict(value)
        return cls(
            ollama_host=str(raw.get("ollama_host") or "http://127.0.0.1:11434").strip(),
            openai_api_key=str(raw.get("openai_api_key") or "").strip(),
            openai_base_url=str(
                raw.get("openai_base_url") or "https://api.openai.com/v1"
            ).strip(),
            anthropic_api_key=str(raw.get("anthropic_api_key") or "").strip(),
            deepseek_api_key=str(raw.get("deepseek_api_key") or "").strip(),
            deepseek_base_url=str(
                raw.get("deepseek_base_url") or "https://api.deepseek.com/v1"
            ).strip(),
            roles=roles,
        )

    @classmethod
    def defaults(cls) -> AIOrchestratorSettings:
        return cls.from_mapping({"roles": dict(DEFAULT_ROLE_BINDINGS)})
