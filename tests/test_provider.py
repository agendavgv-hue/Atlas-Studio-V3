"""Reliability: AI provider generate + sequential requests + failure recovery."""

from __future__ import annotations

import unittest

from atlas.ai.models.ai_request import AIRequest

from tests.reliability_support import (
    bootstrap_ai_stack,
    default_ollama_model,
    ollama_available,
)


class ProviderReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_manager, cls.ai_service, cls.plugin, cls.settings = bootstrap_ai_stack()
        if not ollama_available(cls.runtime_manager):
            raise unittest.SkipTest("Ollama runtime not available")
        cls.model = default_ollama_model(cls.settings)
        if not cls.model:
            # Fall back to first installed model from provider.
            provider = cls.ai_service.orchestrator.get_provider("ollama")
            models = list(provider.list_models())
            if not models:
                raise unittest.SkipTest("No Ollama models installed")
            cls.model = models[0]

    def test_check_provider_ok(self) -> None:
        result = self.ai_service.check_provider("ollama")
        self.assertTrue(result.get("ok"), msg=str(result))

    def test_short_generate_via_role(self) -> None:
        response = self.ai_service.generate(
            role="creative_director",
            prompt="Reply with exactly: OK",
            model=self.model,
            max_tokens=32,
            temperature=0.0,
        )
        self.assertTrue(response.success, msg=response.error)
        self.assertTrue(str(response.text or "").strip())

    def test_short_generate_via_orchestrator(self) -> None:
        response = self.ai_service.orchestrator.generate(
            AIRequest(
                prompt="Reply with exactly: OK",
                model=self.model,
                max_tokens=32,
                temperature=0.0,
            ),
            provider_id="ollama",
        )
        self.assertTrue(response.success, msg=response.error)
        self.assertTrue(str(response.text or "").strip())

    def test_multiple_sequential_requests(self) -> None:
        texts: list[str] = []
        for i in range(3):
            response = self.ai_service.generate(
                role="creative_director",
                prompt=f"Reply with the single digit {i} and nothing else.",
                model=self.model,
                max_tokens=16,
                temperature=0.0,
            )
            self.assertTrue(response.success, msg=f"seq[{i}]: {response.error}")
            texts.append(str(response.text or "").strip())
        self.assertEqual(len(texts), 3)
        self.assertTrue(all(texts), msg=f"Empty sequential responses: {texts!r}")

    def test_recovery_after_provider_failure(self) -> None:
        failed = self.ai_service.generate(
            role="creative_director",
            prompt="hello",
            model="atlas-reliability-missing-model-xyz",
            max_tokens=16,
            temperature=0.0,
        )
        self.assertFalse(failed.success, msg="Expected missing-model failure")

        recovered = self.ai_service.generate(
            role="creative_director",
            prompt="Reply with exactly: RECOVERED",
            model=self.model,
            max_tokens=32,
            temperature=0.0,
        )
        self.assertTrue(recovered.success, msg=recovered.error)
        self.assertTrue(str(recovered.text or "").strip())


if __name__ == "__main__":
    unittest.main()
