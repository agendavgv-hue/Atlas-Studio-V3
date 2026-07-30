"""Regression: Script → Production Sheet → Images must share one sheet format."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.pipelines.artifacts import PRODUCTION_SHEET_FILENAME, SCRIPT_FOLDER
from app.pipelines.context import ChannelDefaults
from app.pipelines.engine import ProductionEngine
from app.pipelines.image_naming import image_basename
from app.pipelines.results import PipelineOutcome
from app.pipelines.sheet_format import CANONICAL_SHEET_EXAMPLE
from app.pipelines.sheet_prompts import extract_image_prompts
from app.projects.project_service import ProjectService
from app.providers.base import TextProvider
from app.providers.image_base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)
from app.prompts.defaults import PRODUCTION_SHEET_PIPELINE_INSTRUCTION


class _FakeText(TextProvider):
    def __init__(self) -> None:
        self.calls: list[str] = []

    @property
    def provider_id(self) -> str:
        return "fake-text"

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        self.calls.append(prompt)
        blob = f"{system or ''}\n{prompt}".casefold()
        if "image 01" in blob or "production sheet" in blob or "convert the narration" in blob:
            return CANONICAL_SHEET_EXAMPLE
        return "Narration about Atlantis under the waves."


class _FakeImage(ImageProvider):
    def __init__(self) -> None:
        self.calls: list[ImageGenerationRequest] = []

    @property
    def provider_id(self) -> str:
        return "fake-image"

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self.calls.append(request)
        return ImageGenerationResponse(
            image_png=b"\x89PNG" + f"{len(self.calls)}".encode(),
            seed=1,
            model="fake",
            width=512,
            height=512,
        )

    def list_models(self) -> list[str]:
        return ["fake"]

    def test_connection(self) -> str:
        return "ok"

    def validate_ready(self) -> None:
        return None


class ProductionToImagesRegressionTests(unittest.TestCase):
    def test_instruction_requests_canonical_image_blocks(self) -> None:
        text = PRODUCTION_SHEET_PIPELINE_INSTRUCTION
        self.assertIn("IMAGE 01", text)
        self.assertIn("Prompt:", text)
        self.assertIn("Do not replace Prompt:", text)

    def test_script_production_images_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "atlas"
            project_root = root / "youtube"
            channel = "Hollow Atlas"
            (project_root / channel).mkdir(parents=True)
            config = AppConfig(data_root=data_root, project_root=project_root)
            config.image_provider = "forge"
            Storage(config).ensure_structure()
            projects = ProjectService(config)
            project = projects.create_project(channel, "Atlantis")
            text = _FakeText()
            images = _FakeImage()
            engine = ProductionEngine(
                projects,
                config,
                text_provider=text,
                image_provider=images,
            )
            context = engine.build_context(
                project,
                channel_defaults=ChannelDefaults(name=channel),
            )

            production = engine.generate_production(context)
            self.assertEqual(production.outcome, PipelineOutcome.SUCCESS)

            sheet_path = context.folder(SCRIPT_FOLDER) / PRODUCTION_SHEET_FILENAME
            self.assertTrue(sheet_path.is_file())
            sheet_text = sheet_path.read_text(encoding="utf-8")
            prompts = extract_image_prompts(sheet_text)
            self.assertEqual(len(prompts), 3)

            # Instruction asked of the model must mention canonical layout.
            sheet_call = text.calls[1]
            self.assertIn("IMAGE 01", sheet_call)
            self.assertIn("Prompt:", sheet_call)

            image_result = engine.generate_images(context)
            self.assertEqual(image_result.outcome, PipelineOutcome.SUCCESS)
            self.assertEqual(image_result.queue_total, 3)
            self.assertEqual(len(images.calls), 3)
            for index in (1, 2):
                self.assertTrue(
                    (context.folder("images") / image_basename(index)).is_file()
                )

    def test_legacy_scene_layout_without_prompt_is_not_written(self) -> None:
        """Unusable Scene/Visual sheets must fail before Images sees them."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "atlas"
            project_root = root / "youtube"
            channel = "Hollow Atlas"
            (project_root / channel).mkdir(parents=True)
            config = AppConfig(data_root=data_root, project_root=project_root)
            Storage(config).ensure_structure()
            projects = ProjectService(config)
            project = projects.create_project(channel, "Atlantis")

            class BadSheet(TextProvider):
                @property
                def provider_id(self) -> str:
                    return "bad"

                def generate_text(self, prompt: str, *, system: str | None = None) -> str:
                    blob = f"{system or ''}\n{prompt}".casefold()
                    if "image 01" in blob or "production" in blob:
                        return "Scene 1\nVisual: pretty ruins\nDuration: 5s\n"
                    return "Script text."

            engine = ProductionEngine(
                projects,
                config,
                text_provider=BadSheet(),
            )
            context = engine.build_context(project)
            result = engine.generate_production(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertFalse(
                (context.folder(SCRIPT_FOLDER) / PRODUCTION_SHEET_FILENAME).is_file()
            )


if __name__ == "__main__":
    unittest.main()
