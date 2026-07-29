"""Phase 2 tests — channel system."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.channels.channel_discovery import (
    DEFAULT_IGNORED_CHANNEL_FOLDERS,
    discover_channel_folder_names,
)
from app.channels.channel_service import ChannelService
from app.channels.models import Channel
from app.core.app_config import AppConfig
from app.core.storage import Storage


def _service(tmp: Path) -> tuple[ChannelService, Path, Path]:
    data_root = tmp / "atlas_data"
    project_root = tmp / "youtube"
    project_root.mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    storage = Storage(config)
    storage.ensure_structure()
    return ChannelService(storage, config), data_root, project_root


class ChannelDiscoveryTests(unittest.TestCase):
    def test_discovers_existing_folders_without_hardcoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Hollow Atlas").mkdir()
            (root / "Mirror Drift").mkdir()
            (root / ".hidden").mkdir()
            (root / "notes.txt").write_text("x", encoding="utf-8")

            names = discover_channel_folder_names(root)

            self.assertEqual(names, ["Hollow Atlas", "Mirror Drift"])

    def test_default_ignore_list_includes_master(self) -> None:
        self.assertIn("MASTER", DEFAULT_IGNORED_CHANNEL_FOLDERS)

    def test_ignores_master_folder_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Hollow Atlas").mkdir()
            (root / "MASTER").mkdir()

            names = discover_channel_folder_names(root)

            self.assertEqual(names, ["Hollow Atlas"])
            self.assertNotIn("MASTER", names)

    def test_custom_ignore_list_is_configurable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Keep").mkdir()
            (root / "SkipMe").mkdir()
            (root / "MASTER").mkdir()

            names = discover_channel_folder_names(root, ignored_folders=("SkipMe",))

            self.assertEqual(names, ["Keep", "MASTER"])


class ChannelServiceTests(unittest.TestCase):
    def test_create_channel_makes_library_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, data_root, project_root = _service(Path(tmp))
            channel = service.create_channel("Future Channel 1")

            self.assertEqual(channel.name, "Future Channel 1")
            self.assertTrue((project_root / "Future Channel 1").is_dir())
            config_file = data_root / "Channels" / "Future Channel 1" / "channel.json"
            self.assertTrue(config_file.is_file())
            payload = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["name"], "Future Channel 1")
            self.assertIn("image_prompt", payload)
            self.assertIn("voice", payload)

    def test_existing_folder_gets_default_config_on_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, data_root, project_root = _service(Path(tmp))
            (project_root / "Hollow Atlas").mkdir()

            channels = service.list_channels()

            self.assertEqual([c.name for c in channels], ["Hollow Atlas"])
            self.assertTrue(
                (data_root / "Channels" / "Hollow Atlas" / "channel.json").is_file()
            )

    def test_list_skips_ignored_master_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, data_root, project_root = _service(Path(tmp))
            (project_root / "Hollow Atlas").mkdir()
            (project_root / "MASTER").mkdir()

            channels = service.list_channels()

            self.assertEqual([c.name for c in channels], ["Hollow Atlas"])
            self.assertFalse((data_root / "Channels" / "MASTER").exists())

    def test_unlimited_synthetic_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = _service(Path(tmp))
            created = [service.create_channel(f"Channel {i}") for i in range(5)]
            listed = service.list_channels()
            self.assertEqual(len(created), 5)
            self.assertEqual(len(listed), 5)

    def test_select_channel_sets_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = _service(Path(tmp))
            service.create_channel("Mirror Drift")
            selected = service.select_channel("Mirror Drift")
            self.assertEqual(selected.folder_name, "Mirror Drift")
            self.assertEqual(service.active_channel_name, "Mirror Drift")

    def test_rejects_empty_and_invalid_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = _service(Path(tmp))
            with self.assertRaises(ValueError):
                service.create_channel("  ")
            with self.assertRaises(ValueError):
                service.create_channel("bad/name")

    def test_list_without_project_root_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "atlas"
            config = AppConfig(data_root=data_root, project_root=None)
            storage = Storage(config)
            storage.ensure_structure()
            service = ChannelService(storage, config)
            self.assertEqual(service.list_channels(), [])


class ChannelModelTests(unittest.TestCase):
    def test_round_trip_dict(self) -> None:
        channel = Channel.create_default("Test Channel")
        restored = Channel.from_dict(channel.to_dict(), fallback_name="fallback")
        self.assertEqual(restored.name, "Test Channel")
        self.assertEqual(restored.folder_name, "Test Channel")


class AppConfigProjectRootTests(unittest.TestCase):
    def test_project_root_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_file = tmp_path / "config.json"
            data_root = tmp_path / "data"
            project_root = tmp_path / "youtube"

            with patch("app.core.app_config.bootstrap_config_path", return_value=config_file):
                original = AppConfig(data_root=data_root, project_root=project_root)
                original.save()
                loaded = AppConfig.load(default_root=tmp_path / "fallback")

            self.assertEqual(loaded.project_root, project_root.resolve())


class NoProjectDependencyTests(unittest.TestCase):
    def test_channel_package_does_not_import_projects(self) -> None:
        import app.channels.channel_service as service_mod
        import app.channels.channel_store as store_mod
        import app.channels.models as models_mod

        for module in (service_mod, store_mod, models_mod):
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertNotIn("project_service", source.lower())
            self.assertNotIn("from app.projects", source)
            self.assertNotIn("import app.projects", source)


if __name__ == "__main__":
    unittest.main()
