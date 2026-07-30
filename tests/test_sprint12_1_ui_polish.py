"""UI-only tests for Sprint 12.1 polish helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.providers.health import HealthCheckItem, ProviderHealth
from app.ui.voice_health_display import (
    display_from_kokoro_health,
    probe_kokoro_quick,
)
from app.ui.widgets.status_card import StatusCard, _format_seconds


class VoiceHealthDisplayTests(unittest.TestCase):
    def test_maps_package_missing(self) -> None:
        health = ProviderHealth(
            ok=False,
            provider_id="kokoro",
            message="failed",
            checks=(HealthCheckItem("kokoro_onnx", False, "missing"),),
        )
        display = display_from_kokoro_health(health)
        self.assertEqual(display.level, "error")
        self.assertIn("Package missing", display.title)
        self.assertTrue(display.headline.startswith("🔴"))

    def test_maps_models_missing(self) -> None:
        health = ProviderHealth(
            ok=False,
            provider_id="kokoro",
            message="failed",
            checks=(
                HealthCheckItem("kokoro_onnx", True, "ok"),
                HealthCheckItem("onnxruntime", True, "ok"),
                HealthCheckItem("model_files", False, "missing"),
            ),
        )
        display = display_from_kokoro_health(health)
        self.assertEqual(display.level, "warn")
        self.assertEqual(display.title, "Models not downloaded")
        self.assertIn("not been downloaded", display.detail)

    def test_maps_ready(self) -> None:
        health = ProviderHealth(
            ok=True,
            provider_id="kokoro",
            message="healthy",
            checks=(
                HealthCheckItem("kokoro_onnx", True, "ok"),
                HealthCheckItem("onnxruntime", True, "ok"),
                HealthCheckItem("model_files", True, "ok"),
                HealthCheckItem("synthesis", True, "ok"),
            ),
        )
        display = display_from_kokoro_health(health)
        self.assertEqual(display.level, "ok")
        self.assertEqual(display.title, "Kokoro Ready")
        self.assertTrue(display.headline.startswith("🟢"))

    def test_probe_reports_missing_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            display = probe_kokoro_quick(model_dir=Path(tmp))
        # Without installed packages this may be package/runtime missing;
        # with packages installed, models missing.
        self.assertIn(display.level, {"error", "warn"})


class StatusCardHelperTests(unittest.TestCase):
    def test_format_seconds(self) -> None:
        self.assertEqual(_format_seconds(None), "—")
        self.assertEqual(_format_seconds(42), "00:42")
        self.assertEqual(_format_seconds(198), "03:18")

    def test_status_card_progress(self) -> None:
        from PySide6.QtWidgets import QApplication
        import sys

        app = QApplication.instance() or QApplication(sys.argv)
        card = StatusCard()
        card.set_progress(
            task="Generating Images",
            current=1,
            total=15,
            item="IMAGE 01",
            elapsed_seconds=42,
            eta_seconds=198,
        )
        self.assertEqual(card._task.text(), "Generating Images")
        self.assertEqual(card._progress_text.text(), "1 / 15")
        self.assertEqual(card._item.text(), "IMAGE 01")
        self.assertEqual(card._elapsed.text(), "00:42")
        self.assertEqual(card._eta.text(), "03:18")
        self.assertEqual(card._bar.value(), 1)
        self.assertEqual(card._bar.maximum(), 15)
        card.set_from_status_text("Ready")
        self.assertEqual(card._task.text(), "Ready")
        _ = app


if __name__ == "__main__":
    unittest.main()
