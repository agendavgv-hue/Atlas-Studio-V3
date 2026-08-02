"""Ollama text provider — local Qwen / Gemma / DeepSeek / etc."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.providers.base import TextProvider
from app.providers.errors import ProviderError


class OllamaTextProvider(TextProvider):
    """OpenAI-compatible chat via local Ollama HTTP API."""

    def __init__(
        self,
        *,
        host: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:14b",
        timeout_s: float = 180.0,
    ) -> None:
        self._host = (host or "http://127.0.0.1:11434").rstrip("/")
        self._model = (model or "qwen2.5:14b").strip()
        self._timeout = float(timeout_s)

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        if not (prompt or "").strip():
            raise ProviderError("Ollama prompt is empty.")
        if not self._model:
            raise ProviderError("Ollama model is not configured.")

        messages: list[dict[str, str]] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt.strip()})

        # Prefer /api/chat; fall back to OpenAI-compatible endpoint.
        try:
            return self._chat_native(messages)
        except ProviderError:
            return self._chat_openai_compat(messages)

    def _chat_native(self, messages: list[dict[str, str]]) -> str:
        url = f"{self._host}/api/chat"
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.4},
        }
        data = _post_json(url, payload, timeout=self._timeout)
        message = data.get("message") if isinstance(data.get("message"), dict) else {}
        text = str(message.get("content") or "").strip()
        if not text:
            raise ProviderError("Ollama returned an empty response.")
        return text

    def _chat_openai_compat(self, messages: list[dict[str, str]]) -> str:
        url = f"{self._host}/v1/chat/completions"
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.4,
        }
        data = _post_json(url, payload, timeout=self._timeout)
        choices = data.get("choices") if isinstance(data.get("choices"), list) else []
        if not choices:
            raise ProviderError("Ollama OpenAI-compat returned no choices.")
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        text = str((message or {}).get("content") or "").strip()
        if not text:
            raise ProviderError("Ollama returned an empty response.")
        return text


def discover_ollama_models(host: str = "http://127.0.0.1:11434") -> list[str]:
    """List local Ollama model tags."""
    base = (host or "http://127.0.0.1:11434").rstrip("/")
    url = f"{base}/api/tags"
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"Ollama HTTP {exc.code} while listing models.") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(
            f"Cannot reach Ollama at {base}. Is Ollama running?"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Ollama model list failed: {exc}") from exc

    models: list[str] = []
    for entry in payload.get("models") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or entry.get("model") or "").strip()
        if name:
            models.append(name)
    return sorted(dict.fromkeys(models))


def ollama_reachable(host: str = "http://127.0.0.1:11434") -> bool:
    try:
        discover_ollama_models(host)
        return True
    except ProviderError:
        return False


def _post_json(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"Ollama HTTP {exc.code}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Cannot reach Ollama: {exc}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Ollama request failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProviderError("Ollama returned a non-object JSON payload.")
    return raw
