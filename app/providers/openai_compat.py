"""OpenAI-compatible text provider (OpenAI, DeepSeek, local gateways)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.providers.base import TextProvider
from app.providers.errors import ProviderError


class OpenAICompatTextProvider(TextProvider):
    """Chat Completions API used by OpenAI, DeepSeek, and many gateways."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        provider_id: str = "openai",
        timeout_s: float = 120.0,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._model = (model or "").strip()
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._id = (provider_id or "openai").strip().casefold() or "openai"
        self._timeout = float(timeout_s)

    @property
    def provider_id(self) -> str:
        return self._id

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        if not self._api_key:
            raise ProviderError(f"{self._id} API key is empty.")
        if not self._model:
            raise ProviderError(f"{self._id} model is not configured.")
        if not (prompt or "").strip():
            raise ProviderError(f"{self._id} prompt is empty.")

        messages: list[dict[str, str]] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt.strip()})

        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.4,
        }
        data = _post_json(url, payload, api_key=self._api_key, timeout=self._timeout)
        choices = data.get("choices") if isinstance(data.get("choices"), list) else []
        if not choices or not isinstance(choices[0], dict):
            raise ProviderError(f"{self._id} returned no choices.")
        message = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
        text = str(message.get("content") or "").strip()
        if not text:
            raise ProviderError(f"{self._id} returned an empty response.")
        return text


class AnthropicTextProvider(TextProvider):
    """Anthropic Messages API (Claude)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        timeout_s: float = 120.0,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._model = (model or "claude-sonnet-4-20250514").strip()
        self._timeout = float(timeout_s)

    @property
    def provider_id(self) -> str:
        return "anthropic"

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        if not self._api_key:
            raise ProviderError("Anthropic API key is empty.")
        if not self._model:
            raise ProviderError("Anthropic model is not configured.")
        if not (prompt or "").strip():
            raise ProviderError("Anthropic prompt is empty.")

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt.strip()}],
        }
        if system and system.strip():
            payload["system"] = system.strip()

        url = "https://api.anthropic.com/v1/messages"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Anthropic HTTP {exc.code}: {detail[:400]}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"Cannot reach Anthropic: {exc}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Anthropic request failed: {exc}") from exc

        blocks = data.get("content") if isinstance(data.get("content"), list) else []
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        text = "\n".join(p for p in parts if p).strip()
        if not text:
            raise ProviderError("Anthropic returned an empty response.")
        return text


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"HTTP {exc.code}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Network error: {exc}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Request failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProviderError("Provider returned a non-object JSON payload.")
    return raw
