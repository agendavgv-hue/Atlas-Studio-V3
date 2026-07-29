"""Gemini model discovery tests — no hardcoded model assumptions."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.providers.errors import ProviderError
from app.providers.gemini import discover_text_models


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


class DiscoverTextModelsTests(unittest.TestCase):
    def test_lists_generate_content_models_only(self) -> None:
        payload = {
            "models": [
                {
                    "name": "models/alpha-text",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/embed-only",
                    "supportedGenerationMethods": ["embedContent"],
                },
                {
                    "name": "models/beta-text",
                    "supportedGenerationMethods": ["generateContent", "countTokens"],
                },
            ]
        }
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)):
            models = discover_text_models("valid-key")
        self.assertEqual(models, ["alpha-text", "beta-text"])

    def test_empty_models_raises_clear_error(self) -> None:
        with patch("urllib.request.urlopen", return_value=_FakeResponse({"models": []})):
            with self.assertRaises(ProviderError) as ctx:
                discover_text_models("valid-key")
        self.assertIn("No Gemini text models", str(ctx.exception))

    def test_empty_api_key_rejected(self) -> None:
        with self.assertRaises(ProviderError):
            discover_text_models("   ")


if __name__ == "__main__":
    unittest.main()
