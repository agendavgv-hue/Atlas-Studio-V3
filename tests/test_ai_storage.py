"""Tests for Atlas AI Models storage ownership."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core import ai_storage
from app.core.ai_storage import (
    PROVIDER_SUBDIRS,
    apply_ai_storage_environment,
    ensure_ai_models_layout,
    format_bytes,
    format_eta,
    huggingface_dir,
    migrate_legacy_huggingface_cache,
)
from app.core.app_config import AppConfig
from app.providers.chatterbox_install import (
    CHATTERBOX_ENGLISH_FILES,
    ChatterboxModelMissingError,
    is_chatterbox_english_installed,
    require_chatterbox_english,
)


class AiStoragePathsTests(unittest.TestCase):
    def test_ensure_layout_creates_provider_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "AI" / "Models"
            resolved = ensure_ai_models_layout(root)
            self.assertEqual(resolved, root.resolve())
            for name in PROVIDER_SUBDIRS:
                self.assertTrue((resolved / name).is_dir(), msg=name)

    def test_apply_environment_sets_hf_and_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Models"
            apply_ai_storage_environment(root)
            hf = str(huggingface_dir(root))
            self.assertEqual(os.environ.get("HF_HOME"), hf)
            self.assertEqual(os.environ.get("HF_HUB_CACHE"), hf)
            self.assertEqual(os.environ.get("TRANSFORMERS_CACHE"), hf)
            self.assertEqual(os.environ.get("HUGGINGFACE_HUB_CACHE"), hf)
            self.assertEqual(
                os.environ.get("OLLAMA_MODELS"),
                str((root / "Ollama").resolve()),
            )

    def test_peek_reads_config_without_qt_app(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.json"
            models = Path(tmp) / "custom_models"
            cfg.write_text(
                json.dumps({"ai_models_root": str(models)}),
                encoding="utf-8",
            )
            with patch(
                "app.core.ai_storage._candidate_config_paths",
                return_value=[cfg],
            ):
                peeked = ai_storage.peek_ai_models_root_from_disk()
            self.assertEqual(peeked, models.resolve())

    def test_format_helpers(self) -> None:
        self.assertIn("GB", format_bytes(3.2 * 1024**3))
        self.assertEqual(format_eta(45), "45s")
        self.assertEqual(format_eta(125), "2m 5s")
        self.assertEqual(format_eta(None), "—")


class AiStorageMigrationTests(unittest.TestCase):
    def test_migrate_moves_legacy_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            legacy = tmp_path / ".cache" / "huggingface"
            hub = legacy / "hub"
            hub.mkdir(parents=True)
            sample = hub / "models--demo"
            sample.mkdir()
            (sample / "config.json").write_text("{}", encoding="utf-8")

            dest = tmp_path / "AI" / "Models" / "HuggingFace"
            with patch(
                "app.core.ai_storage.legacy_huggingface_cache",
                return_value=legacy.resolve(),
            ):
                result = migrate_legacy_huggingface_cache(dest)

            self.assertEqual(result.moved, 1)
            self.assertTrue((dest / "hub" / "models--demo" / "config.json").is_file())
            # Legacy tree should be empty or removed after a full move.
            if legacy.exists():
                self.assertEqual(list(legacy.iterdir()), [])


class AppConfigAiModelsTests(unittest.TestCase):
    def test_round_trip_ai_models_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_file = tmp_path / "config.json"
            data_root = tmp_path / "studio"
            models = tmp_path / "AI" / "Models"

            with patch("app.core.app_config.bootstrap_config_path", return_value=config_file):
                original = AppConfig(data_root=data_root, ai_models_root=models)
                original.save()
                loaded = AppConfig.load(default_root=tmp_path / "fallback")

            self.assertEqual(loaded.ai_models_root, models.resolve())
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(Path(saved["ai_models_root"]), models.resolve())


class ChatterboxInstallTests(unittest.TestCase):
    def test_missing_model_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Models"
            ensure_ai_models_layout(root)
            self.assertFalse(is_chatterbox_english_installed(root))
            with self.assertRaises(ChatterboxModelMissingError):
                require_chatterbox_english(root)

    def test_installed_when_files_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Models"
            ensure_ai_models_layout(root)
            chatter = root / "Chatterbox"
            for name in CHATTERBOX_ENGLISH_FILES:
                (chatter / name).write_bytes(b"x")
            self.assertTrue(is_chatterbox_english_installed(root))
            self.assertEqual(require_chatterbox_english(root), chatter.resolve())


if __name__ == "__main__":
    unittest.main()
