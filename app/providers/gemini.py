"""Google Gemini text provider and model discovery."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.providers.base import TextProvider
from app.providers.errors import ProviderError

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


def discover_text_models(api_key: str) -> list[str]:
    """Validate the API key by listing models that support generateContent.

    Returns model ids without the ``models/`` prefix, sorted uniquely.
    Raises ``ProviderError`` when the key is invalid or the API fails.
    Raises ``ProviderError`` when the API returns no usable text models.
    """
    key = api_key.strip()
    if not key:
        raise ProviderError("Gemini API key is empty.")

    models: list[str] = []
    page_token = ""
    while True:
        query: dict[str, str] = {"key": key, "pageSize": "100"}
        if page_token:
            query["pageToken"] = page_token
        url = f"{_API_ROOT}?{urllib.parse.urlencode(query)}"
        body = _get_json(url)
        for entry in body.get("models") or []:
            model_id = _text_model_id(entry)
            if model_id:
                models.append(model_id)
        page_token = str(body.get("nextPageToken") or "").strip()
        if not page_token:
            break

    unique = sorted(dict.fromkeys(models))
    if not unique:
        raise ProviderError(
            "No Gemini text models were returned for this API key. "
            "Confirm the key has access to the Generative Language API."
        )
    return unique


def _text_model_id(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    methods = entry.get("supportedGenerationMethods") or []
    if "generateContent" not in methods:
        return None
    name = str(entry.get("name") or "").strip()
    if not name:
        return None
    if name.startswith("models/"):
        name = name[len("models/") :]
    return name or None


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code in {401, 403}:
            raise ProviderError(
                f"Gemini API key was rejected (HTTP {exc.code}). Check the key in Settings."
            ) from exc
        raise ProviderError(f"Gemini HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Gemini network error: {exc}") from exc

    if not isinstance(payload, dict):
        raise ProviderError(f"Unexpected Gemini models response: {payload}")
    return payload


class GeminiTextProvider(TextProvider):
    def __init__(self, api_key: str, *, model: str) -> None:
        key = api_key.strip()
        if not key:
            raise ProviderError("Gemini API key is empty.")
        chosen = model.strip()
        if not chosen:
            raise ProviderError(
                "No Gemini model is selected. "
                "Open Settings, click Test Connection, and choose a model."
            )
        self._api_key = key
        self._model = chosen

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        url = f"{_API_ROOT}/{self._model}:generateContent?key={self._api_key}"
        user_text = prompt if not system else f"{system.strip()}\n\n{prompt.strip()}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Gemini HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"Gemini network error: {exc}") from exc

        try:
            parts = body["candidates"][0]["content"]["parts"]
            text = "".join(str(part.get("text", "")) for part in parts).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected Gemini response: {body}") from exc

        if not text:
            raise ProviderError("Gemini returned empty text.")
        return text
