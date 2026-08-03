"""Reliability: RuntimeManager autostart / health."""

from __future__ import annotations

import unittest

from atlas.runtime.models import RuntimeStatus

from tests.reliability_support import bootstrap_ai_stack, ollama_available


class RuntimeAutostartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_manager, cls.ai_service, cls.plugin, cls.settings = bootstrap_ai_stack()
        if not ollama_available(cls.runtime_manager):
            raise unittest.SkipTest("Ollama runtime not available")

    def test_ensure_running_reports_running(self) -> None:
        info = self.runtime_manager.ensure_running("ollama")
        self.assertTrue(info.is_running, msg=str(info))
        self.assertEqual(info.status, RuntimeStatus.RUNNING)

    def test_ensure_running_idempotent(self) -> None:
        first = self.runtime_manager.ensure_running("ollama")
        second = self.runtime_manager.ensure_running("ollama")
        self.assertTrue(first.is_running)
        self.assertTrue(second.is_running)
        self.assertEqual(first.started_by_atlas, second.started_by_atlas)

    def test_runtime_info_after_ensure(self) -> None:
        self.runtime_manager.ensure_running("ollama")
        info = self.runtime_manager.info("ollama")
        self.assertTrue(info.is_running)
        self.assertTrue(info.is_installed or info.is_running)


if __name__ == "__main__":
    unittest.main()
