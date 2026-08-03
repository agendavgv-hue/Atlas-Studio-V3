"""Reliability: streaming generation path (Ollama stream=true)."""

from __future__ import annotations

import unittest

from atlas.ai.models.ai_request import AIRequest
from plugins.ollama.provider import _merge_stream_chunks, extract_assistant_text

from tests.reliability_support import (
    bootstrap_ai_stack,
    default_ollama_model,
    ollama_available,
)


class StreamingUnitTests(unittest.TestCase):
    def test_merge_stream_chunks_aggregates_response(self) -> None:
        chunks = [
            {"response": "Hel", "done": False},
            {"response": "lo", "done": False},
            {"response": "", "done": True},
        ]
        merged = _merge_stream_chunks(chunks)
        self.assertEqual(merged.get("response"), "Hello")
        self.assertEqual(merged.get("_aggregated_text"), "Hello")

    def test_merge_stream_chunks_chat_message_content(self) -> None:
        chunks = [
            {"message": {"role": "assistant", "content": "A"}, "done": False},
            {"message": {"role": "assistant", "content": "B"}, "done": True},
        ]
        merged = _merge_stream_chunks(chunks)
        text = extract_assistant_text(merged)
        self.assertIn("A", text)
        self.assertIn("B", text)


class StreamingLiveTests(unittest.TestCase):
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

    def test_streaming_emits_progress_and_completes(self) -> None:
        progress_events: list[str] = []

        response = self.ai_service.generate(
            role="creative_director",
            prompt="Write one short sentence about rivers.",
            model=self.model,
            max_tokens=64,
            temperature=0.2,
            on_progress=progress_events.append,
        )
        self.assertTrue(response.success, msg=response.error)
        self.assertTrue(str(response.text or "").strip())
        self.assertGreaterEqual(
            len(progress_events),
            1,
            msg=f"Expected streaming progress events, got {progress_events!r}",
        )

    def test_provider_stream_completes_with_text(self) -> None:
        provider = self.ai_service.orchestrator.get_provider("ollama")
        provider._progress_hook = None
        response = provider.generate(
            AIRequest(
                prompt="Say hi in three words.",
                model=self.model,
                max_tokens=24,
                temperature=0.0,
            )
        )
        self.assertTrue(response.success, msg=response.error)
        self.assertTrue(str(response.text or "").strip())


if __name__ == "__main__":
    unittest.main()
