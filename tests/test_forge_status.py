"""Tests for Forge status service and settings lifecycle flags."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.core.forge_settings import ForgeSettings
from app.providers.backend_status import BackendStatus
from app.providers.forge_status import ForgeStatusService


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class ForgeSettingsTests(unittest.TestCase):
    def test_defaults_enable_auto_start(self) -> None:
        settings = ForgeSettings()
        self.assertTrue(settings.auto_start_forge)
        self.assertFalse(settings.close_forge_on_exit)
        self.assertEqual(settings.port, 7860)

    def test_round_trip_lifecycle_flags(self) -> None:
        raw = ForgeSettings(
            launch_path=r"D:\Forge\webui-user.bat",
            auto_start_forge=False,
            close_forge_on_exit=True,
        ).to_dict()
        loaded = ForgeSettings.from_mapping(raw)
        self.assertFalse(loaded.auto_start_forge)
        self.assertTrue(loaded.close_forge_on_exit)
        self.assertEqual(loaded.launch_path, r"D:\Forge\webui-user.bat")

    def test_missing_auto_start_defaults_true(self) -> None:
        loaded = ForgeSettings.from_mapping({"host": "127.0.0.1", "port": 7860})
        self.assertTrue(loaded.auto_start_forge)


class ForgeStatusServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_app()

    def test_probe_sets_online_offline(self) -> None:
        service = ForgeStatusService(ForgeSettings(auto_start_forge=False))
        with patch.object(service, "probe_online", return_value=True):
            service._on_tick()
        self.assertEqual(service.status, BackendStatus.ONLINE)
        with patch.object(service, "probe_online", return_value=False):
            service._on_tick()
        self.assertEqual(service.status, BackendStatus.OFFLINE)

    def test_ensure_running_skips_when_already_online(self) -> None:
        service = ForgeStatusService(
            ForgeSettings(auto_start_forge=True, launch_path=r"D:\fake\webui.bat")
        )
        with patch.object(service, "probe_online", return_value=True):
            with patch.object(service, "start_forge") as start:
                service.ensure_running_if_configured()
                start.assert_not_called()
        self.assertFalse(service.started_by_atlas)
        self.assertEqual(service.status, BackendStatus.ONLINE)

    def test_ensure_running_disabled_does_nothing(self) -> None:
        service = ForgeStatusService(
            ForgeSettings(auto_start_forge=False, launch_path=r"D:\fake\webui.bat")
        )
        with patch.object(service, "start_forge") as start:
            service.ensure_running_if_configured()
            start.assert_not_called()

    def test_stop_forge_ignored_when_not_started_by_atlas(self) -> None:
        service = ForgeStatusService(ForgeSettings())
        with patch("app.providers.forge_status._terminate_process_tree") as kill:
            service.stop_forge()
            kill.assert_not_called()

    def test_release_ownership_clears_flag(self) -> None:
        service = ForgeStatusService(ForgeSettings())
        service._started_by_atlas = True
        service.release_ownership()
        self.assertFalse(service.started_by_atlas)

    def test_backend_status_labels(self) -> None:
        self.assertEqual(BackendStatus.ONLINE.label, "Online")
        self.assertEqual(BackendStatus.OFFLINE.label, "Offline")
        self.assertEqual(BackendStatus.STARTING.label, "Starting...")
        self.assertEqual(BackendStatus.ONLINE.dot, "●")
        self.assertEqual(BackendStatus.ONLINE.emoji, "🟢")
        self.assertEqual(BackendStatus.OFFLINE.emoji, "🔴")
        self.assertEqual(BackendStatus.STARTING.emoji, "🟠")
        self.assertEqual(BackendStatus.ONLINE.display_title, "Forge Online")

    def test_tooltip_online_includes_host_port(self) -> None:
        service = ForgeStatusService(
            ForgeSettings(host="127.0.0.1", port=7860, auto_start_forge=False)
        )
        with patch.object(service, "probe_online", return_value=True):
            service._on_tick()
        tip = service.tooltip_text()
        self.assertIn("Forge Online", tip)
        self.assertIn("Host: 127.0.0.1", tip)
        self.assertIn("Port: 7860", tip)

    def test_tooltip_offline_is_short(self) -> None:
        service = ForgeStatusService(ForgeSettings(auto_start_forge=False))
        with patch.object(service, "probe_online", return_value=False):
            service._on_tick()
        self.assertEqual(service.tooltip_text(), "Forge Offline")


if __name__ == "__main__":
    unittest.main()
