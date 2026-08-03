"""Reliability: cancellation during generation."""

from __future__ import annotations

import time
import unittest

from tests.reliability_support import (
    bootstrap_ai_stack,
    default_ollama_model,
    ollama_available,
    run_in_thread,
    wait_until,
)


class CancellationTests(unittest.TestCase):
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

    def test_cancel_during_generation(self) -> None:
        progress: list[str] = []

        def _generate():
            return self.ai_service.generate(
                role="creative_director",
                prompt=(
                    "Write a very long essay with at least forty paragraphs about "
                    "the history of cartography, exploring every continent in depth."
                ),
                model=self.model,
                max_tokens=2048,
                temperature=0.7,
                on_progress=progress.append,
            )

        thread, results, errors = run_in_thread(_generate)

        # Must wait until the provider stream is active. Cancelling on early
        # AIService progress ("Ensuring AI runtime…") is wiped by clear_cancel()
        # when provider.generate() starts.
        def _stream_active() -> bool:
            joined = " | ".join(progress).casefold()
            return (
                "first token" in joined
                or "streaming started" in joined
                or "token" in joined
            )

        started = wait_until(_stream_active, timeout_s=120.0)
        self.assertTrue(
            started,
            msg=f"Stream never started; progress={progress!r}",
        )

        # Keep hammering cancel until the worker exits (covers read-loop races).
        deadline = time.monotonic() + 30.0
        while thread.is_alive() and time.monotonic() < deadline:
            self.ai_service.cancel_provider("ollama")
            time.sleep(0.05)

        thread.join(timeout=90.0)
        self.assertFalse(thread.is_alive(), "Generation thread did not finish after cancel")
        self.assertFalse(errors, msg=f"Unexpected exceptions: {errors!r}")
        self.assertTrue(results, "No response returned after cancel")
        response = results[0]
        self.assertFalse(
            response.success,
            msg=(
                f"Expected cancelled/failed response, got success "
                f"text={response.text[:200]!r}… progress={progress!r}"
            ),
        )
        self.assertIn("cancel", (response.error or "").casefold())

    def test_generate_after_cancel_still_works(self) -> None:
        # Ensure cancel flag does not permanently poison the provider.
        response = self.ai_service.generate(
            role="creative_director",
            prompt="Reply with exactly: AFTER_CANCEL",
            model=self.model,
            max_tokens=32,
            temperature=0.0,
        )
        self.assertTrue(response.success, msg=response.error)
        self.assertTrue(str(response.text or "").strip())


if __name__ == "__main__":
    unittest.main()
