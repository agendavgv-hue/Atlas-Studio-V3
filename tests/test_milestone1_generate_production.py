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
from app.pipelines.sheet_format import CANONICAL_SHEET_EXAMPLE
from app.pipelines.sheet_prompts import extract_image_prompts
from app.projects.project_service import ProjectService
from app.providers.base import TextProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.registry import ProviderRegistry


class FakeTextProvider(TextProvider):
    """Test-only provider. Must never be used in production."""

    def __init__(self, *, sheet_without_prompts: bool = False) -> None:
        self.calls: list[tuple[str | None, str]] = []
        self._sheet_without_prompts = sheet_without_prompts

    @property
    def provider_id(self) -> str:
        return "fake"

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        self.calls.append((system, prompt))
        blob = f"{system or ''}\n{prompt}".casefold()
        if "production sheet" in blob or "convert the narration" in blob or "image 01" in blob:
            if self._sheet_without_prompts:
                return (
                    "Scene 1\n"
                    "Narration: Opening lines about Atlantis.\n"
                    "Visual: Aerial over ocean ruins.\n"
                    "Duration: 8s\n"
                )
            return CANONICAL_SHEET_EXAMPLE
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

            result = engine.generate_production(context)

            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(len(fake.calls), 2)
            # Project title (without numbering) is the generation topic.
            self.assertIn("Topic: Atlantis", fake.calls[0][1])
            script_path = context.folder(SCRIPT_FOLDER) / SCRIPT_FILENAME
            sheet_path = context.folder(SCRIPT_FOLDER) / PRODUCTION_SHEET_FILENAME
            self.assertTrue(script_path.is_file())
            self.assertTrue(sheet_path.is_file())
            self.assertIn("Atlantis", script_path.read_text(encoding="utf-8"))
            sheet_text = sheet_path.read_text(encoding="utf-8")
            self.assertIn("IMAGE 01", sheet_text)
            self.assertTrue(extract_image_prompts(sheet_text))
            self.assertIn(f"{SCRIPT_FOLDER}/{SCRIPT_FILENAME}", result.artifacts)
            self.assertIn(
                f"{SCRIPT_FOLDER}/{PRODUCTION_SHEET_FILENAME}",
                result.artifacts,
            )

            progress = projects.get_progress(project.channel_name, project.folder_name)
            self.assertTrue(progress.step("script").complete)
            self.assertTrue(progress.step("production_sheet").complete)
            self.assertEqual(projects.lifecycle_status(project.channel_name, project.folder_name), "In Progress")

    def test_production_sheet_rejects_output_without_image_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeTextProvider(sheet_without_prompts=True)
            _, _, _, engine, context = _setup(Path(tmp), provider=fake)
            result = engine.generate_production(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertTrue(
                any("image prompt" in err.casefold() for err in result.errors),
                msg=result.errors,
            )
            sheet_path = context.folder(SCRIPT_FOLDER) / PRODUCTION_SHEET_FILENAME
            self.assertFalse(sheet_path.is_file())

    def test_canonical_sheet_example_is_parseable(self) -> None:
        prompts = extract_image_prompts(CANONICAL_SHEET_EXAMPLE)
        self.assertEqual(len(prompts), 3)
        self.assertIn("ocean ruins", prompts[0].prompt.casefold())

    def test_missing_provider_returns_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, engine, context = _setup(Path(tmp), provider=None)
            result = engine.generate_production(context)
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
            result = engine.regenerate_script(context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(len(fake.calls), 1)
            self.assertIn("Topic: Atlantis", fake.calls[0][1])
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

    def test_registry_passes_configured_gemini_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(
                data_root=Path(tmp) / "atlas",
                project_root=Path(tmp) / "yt",
                text_provider="gemini",
                gemini_api_key="test-key",
                gemini_model="models-from-discovery",
            )
            provider = ProviderRegistry(config).require_text_provider()
            self.assertEqual(provider.provider_id, "gemini")
            self.assertEqual(provider.model, "models-from-discovery")  # type: ignore[attr-defined]

    def test_registry_requires_selected_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(
                data_root=Path(tmp) / "atlas",
                project_root=Path(tmp) / "yt",
                text_provider="gemini",
                gemini_api_key="test-key",
                gemini_model="",
            )
            with self.assertRaises(ProviderConfigurationError) as ctx:
                ProviderRegistry(config).require_text_provider()
            self.assertIn("model", str(ctx.exception).casefold())


if __name__ == "__main__":
    unittest.main()
