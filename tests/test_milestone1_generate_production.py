"""Milestone 1 — Generate Production (Script → Production Sheet)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.pipelines.artifacts import (
    PRODUCTION_SHEET_FILENAME,
    SCRIPT_FILENAME,
    SCRIPT_FOLDER,
)
from app.pipelines.context import ChannelDefaults
from app.pipelines.engine import ProductionEngine
from app.pipelines.results import PipelineOutcome
from app.projects.project_service import ProjectService
from app.providers.base import TextProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.registry import ProviderRegistry


class FakeTextProvider(TextProvider):
    """Test-only provider. Must never be used in production."""

    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str]] = []

    @property
    def provider_id(self) -> str:
        return "fake"

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        self.calls.append((system, prompt))
        blob = f"{system or ''}\n{prompt}".casefold()
        if "production sheet" in blob or "convert the narration" in blob:
            return (
                "Scene 1\n"
                "Narration: Opening lines about Atlantis.\n"
                "Visual: Aerial over ocean ruins.\n"
                "Duration: 8s\n"
            )
        return (
            "Welcome to the lost city of Atlantis.\n\n"
            "Beneath the waves, ancient towers still gleam.\n"
        )


def _setup(tmp: Path, *, provider: TextProvider | None = None, config_ai: bool = False):
    data_root = tmp / "atlas"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    if config_ai:
        config.text_provider = "gemini"
        config.gemini_api_key = "test-key-not-used"
    Storage(config).ensure_structure()
    projects = ProjectService(config)
    project = projects.create_project(channel, "Atlantis", idea="")
    engine = ProductionEngine(projects, config, text_provider=provider)
    context = engine.build_context(
        project,
        channel_defaults=ChannelDefaults(name=channel, image_prompt="cinematic ruins"),
    )
    return config, projects, project, engine, context


class GenerateProductionTests(unittest.TestCase):
    def test_generate_production_writes_artifacts_and_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeTextProvider()
            _, projects, project, engine, context = _setup(Path(tmp), provider=fake)

            result = engine.generate_production(context, topic="Lost city of Atlantis")

            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(len(fake.calls), 2)
            script_path = context.folder(SCRIPT_FOLDER) / SCRIPT_FILENAME
            sheet_path = context.folder(SCRIPT_FOLDER) / PRODUCTION_SHEET_FILENAME
            self.assertTrue(script_path.is_file())
            self.assertTrue(sheet_path.is_file())
            self.assertIn("Atlantis", script_path.read_text(encoding="utf-8"))
            self.assertIn("Scene 1", sheet_path.read_text(encoding="utf-8"))
            self.assertIn(f"{SCRIPT_FOLDER}/{SCRIPT_FILENAME}", result.artifacts)
            self.assertIn(
                f"{SCRIPT_FOLDER}/{PRODUCTION_SHEET_FILENAME}",
                result.artifacts,
            )

            progress = projects.get_progress(project.channel_name, project.folder_name)
            self.assertTrue(progress.step("script").complete)
            self.assertTrue(progress.step("production_sheet").complete)
            self.assertEqual(projects.lifecycle_status(project.channel_name, project.folder_name), "In Progress")

    def test_missing_provider_returns_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, engine, context = _setup(Path(tmp), provider=None)
            result = engine.generate_production(context, topic="Atlantis")
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertTrue(
                any("provider" in err.casefold() for err in result.errors),
                msg=result.errors,
            )

    def test_registry_raises_without_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(data_root=Path(tmp) / "atlas", project_root=Path(tmp) / "yt")
            registry = ProviderRegistry(config)
            with self.assertRaises(ProviderConfigurationError) as ctx:
                registry.require_text_provider()
            self.assertIn("Settings", str(ctx.exception))

    def test_regenerate_script_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeTextProvider()
            _, _, _, engine, context = _setup(Path(tmp), provider=fake)
            result = engine.regenerate_script(context, topic="Atlantis")
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(len(fake.calls), 1)
            self.assertTrue((context.folder(SCRIPT_FOLDER) / SCRIPT_FILENAME).is_file())
            self.assertFalse(
                (context.folder(SCRIPT_FOLDER) / PRODUCTION_SHEET_FILENAME).is_file()
            )

    def test_no_mock_provider_in_production_registry(self) -> None:
        source = Path(__file__).resolve().parents[1] / "app" / "providers" / "registry.py"
        text = source.read_text(encoding="utf-8")
        self.assertNotIn("Mock", text)
        self.assertNotIn("FakeTextProvider", text)
        self.assertNotIn("class Fake", text)
        # Registry must only construct Gemini (or future real providers).
        self.assertIn("GeminiTextProvider", text)
        self.assertNotIn("return Fake", text)
        self.assertNotIn('provider_id == "mock"', text)
        self.assertNotIn('provider_id == "fake"', text)


if __name__ == "__main__":
    unittest.main()
