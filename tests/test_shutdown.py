"""Reliability: runtime shutdown / autostop ownership rules."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from atlas.runtime.runtime_manager import RuntimeManager

from tests.reliability_support import bootstrap_ai_stack, ollama_available


class ShutdownLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_manager, cls.ai_service, cls.plugin, cls.settings = bootstrap_ai_stack()
        if not ollama_available(cls.runtime_manager):
            raise unittest.SkipTest("Ollama runtime not available")

    def test_shutdown_respects_started_by_atlas(self) -> None:
        info_before = self.runtime_manager.ensure_running("ollama")
        results = self.runtime_manager.shutdown()

        self.assertIn("ollama", results)
        try:
            if info_before.started_by_atlas:
                # Atlas-owned → stop attempted (True/False depending on stop success).
                self.assertIsInstance(results["ollama"], bool)
                if results["ollama"]:
                    info_after = self.runtime_manager.info("ollama")
                    self.assertFalse(info_after.started_by_atlas)
            else:
                # External / pre-existing Ollama must not be stopped by Atlas shutdown.
                self.assertFalse(results["ollama"])
                info_after = self.runtime_manager.info("ollama")
                self.assertTrue(
                    info_after.is_running,
                    msg="External Ollama was stopped incorrectly",
                )
        finally:
            # Restore for any remaining suite modules that share this process.
            try:
                self.runtime_manager.ensure_running("ollama")
            except Exception:  # noqa: BLE001
                pass

    def test_stop_skips_when_not_owned(self) -> None:
        runtime = self.runtime_manager.get("ollama")
        if runtime.started_by_atlas:
            self.skipTest("Ollama is Atlas-owned in this session; skip external-ownership check")
        stopped = self.runtime_manager.stop("ollama")
        self.assertFalse(stopped)
        self.assertTrue(runtime.is_running())


class ShutdownUnitTests(unittest.TestCase):
    def test_shutdown_only_stops_atlas_owned(self) -> None:
        """Unit: shutdown iterates ownership without touching foreign runtimes."""
        owned = MagicMock()
        owned.name = "ollama"
        owned.started_by_atlas = True
        owned.stop.return_value = True

        foreign = MagicMock()
        foreign.name = "forge"
        foreign.started_by_atlas = False

        registry = MagicMock()
        registry.all.return_value = [owned, foreign]

        manager = RuntimeManager.__new__(RuntimeManager)
        manager._registry = registry

        results = RuntimeManager.shutdown(manager)
        self.assertTrue(results["ollama"])
        self.assertFalse(results["forge"])
        owned.stop.assert_called_once()
        foreign.stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
