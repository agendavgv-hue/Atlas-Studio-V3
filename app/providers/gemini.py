"""Google Gemini text provider."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.providers.base import TextProvider
from app.providers.errors import ProviderError

_DEFAULT_MODEL = "gemini-2.0-flash"
_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiTextProvider(TextProvider):
    def __init__(self, api_key: str, *, model: str = _DEFAULT_MODEL) -> None:
        key = api_key.strip()
        if not key:
            raise ProviderError("Gemini API key is empty.")
        self._api_key = key
        self._model = model

    @property
    def provider_id(self) -> str:
        return "gemini"

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
