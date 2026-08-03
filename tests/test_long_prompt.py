"""Reliability: large prompts and large completions."""

from __future__ import annotations

import unittest

from tests.reliability_support import (
    bootstrap_ai_stack,
    default_ollama_model,
    ollama_available,
)


def _pad_prompt(min_chars: int) -> str:
    unit = (
        "Atlas reliability filler paragraph about documentary pacing, "
        "voiceover clarity, B-roll selection, and narrative tension. "
    )
    body = (unit * ((min_chars // len(unit)) + 2))[:min_chars]
    return (
        "You are given a long script context below. "
        "Reply with exactly one word: DONE\n\n"
        f"{body}"
    )


class LongPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_manager, cls.ai_service, cls.plugin, cls.settings = bootstrap_ai_stack()
        if not ollama_available(cls.runtime_manager):
            raise unittest.SkipTest("Ollama runtime not available")
        cls.model = default_ollama_model(cls.settings)
        if not cls.model:
            provider = cls.ai_service.orchestrator.get_provider("ollama")
            models = list(provider.list_models())
            if not models:
                raise unittest.SkipTest("No Ollama models installed")
            cls.model = models[0]

    def test_prompt_over_25k_chars(self) -> None:
        prompt = _pad_prompt(25_001)
        self.assertGreater(len(prompt), 25_000)

        response = self.ai_service.generate(
            role="creative_director",
            prompt=prompt,
            model=self.model,
            max_tokens=32,
            temperature=0.0,
        )
        self.assertTrue(response.success, msg=response.error)
        self.assertTrue(str(response.text or "").strip())

    def test_large_completion(self) -> None:
        """Ask for a longer completion; verify substantial output returns."""
        response = self.ai_service.generate(
            role="creative_director",
            prompt=(
                "Write a detailed 12-paragraph educational narration about "
                "how rivers shape landscapes. Use plain prose only."
            ),
            model=self.model,
            max_tokens=1024,
            temperature=0.4,
        )
        self.assertTrue(response.success, msg=response.error)
        text = str(response.text or "").strip()
        self.assertGreaterEqual(len(text), 400, msg=f"Completion too short ({len(text)} chars)")


if __name__ == "__main__":
    unittest.main()
