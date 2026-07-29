"""Phase 1 tests — storage foundation."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.app_config import AppConfig
from app.core.storage import Storage, build_storage
from app.core.storage_paths import (
    ASSETS,
    CACHE,
    CHANNELS,
    EXPORTS,
    LOGS,
    MANAGED_DIRECTORIES,
    PROJECTS,
    StoragePaths,
)


class StoragePathsTests(unittest.TestCase):
    def test_resolves_managed_directories_under_root(self) -> None:
        root = Path(tempfile.mkdtemp())
        paths = StoragePaths(root)

        self.assertEqual(paths.root, root.resolve())
        self.assertEqual(paths.channels, root.resolve() / CHANNELS)
        self.assertEqual(paths.projects, root.resolve() / PROJECTS)
        self.assertEqual(paths.assets, root.resolve() / ASSETS)
        self.assertEqual(paths.cache, root.resolve() / CACHE)
        self.assertEqual(paths.exports, root.resolve() / EXPORTS)
        self.assertEqual(paths.logs, root.resolve() / LOGS)

    def test_directory_names_are_relative_segments(self) -> None:
        for name in MANAGED_DIRECTORIES:
            self.assertFalse(Path(name).is_absolute())
            self.assertEqual(name, Path(name).name)


class StorageTests(unittest.TestCase):
    def test_ensure_structure_creates_missing_folders(self) -> None:
        root = Path(tempfile.mkdtemp()) / "atlas_data"
        config = AppConfig(data_root=root)
        storage = Storage(config)

        self.assertFalse(root.exists())
        storage.ensure_structure()

        self.assertTrue(storage.root.is_dir())
        for directory in (
            storage.channels,
            storage.projects,
            storage.assets,
            storage.cache,
            storage.exports,
            storage.logs,
        ):
            self.assertTrue(directory.is_dir(), msg=str(directory))

    def test_set_data_root_persists_and_creates_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_file = tmp_path / "config.json"
            new_root = tmp_path / "data_root"

            config = AppConfig(data_root=tmp_path / "unused")
            storage = Storage(config)

            with patch("app.core.app_config.bootstrap_config_path", return_value=config_file):
                storage.set_data_root(new_root)

            self.assertEqual(storage.root, new_root.resolve())
            self.assertTrue(storage.channels.is_dir())
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(Path(saved["data_root"]), new_root.resolve())


class AppConfigTests(unittest.TestCase):
    def test_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_file = tmp_path / "config.json"
            data_root = tmp_path / "studio"

            with patch("app.core.app_config.bootstrap_config_path", return_value=config_file):
                original = AppConfig(data_root=data_root)
                original.save()
                loaded = AppConfig.load(default_root=tmp_path / "fallback")

            self.assertEqual(loaded.data_root, data_root.resolve())
            self.assertEqual(loaded.gemini_model, "")


class BuildStorageTests(unittest.TestCase):
    def test_build_storage_loads_config_and_ensures_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_file = tmp_path / "config.json"
            data_root = tmp_path / "app_root"
            data_root.mkdir()

            with patch("app.core.app_config.bootstrap_config_path", return_value=config_file):
                storage = build_storage(default_root=data_root)

            self.assertIsInstance(storage, Storage)
            self.assertEqual(storage.root, data_root.resolve())
            self.assertTrue(storage.channels.is_dir())
            self.assertTrue(storage.logs.is_dir())


if __name__ == "__main__":
    unittest.main()
