"""Sprint 4 tests — Pipeline Framework / ProductionEngine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.pipelines.base import Pipeline
from app.pipelines.context import ChannelDefaults, PipelineContext
from app.pipelines.engine import ProductionEngine
from app.pipelines.registry import PipelineRegistry
from app.pipelines.results import PipelineOutcome, PipelineResult
from app.pipelines.states import PipelineState
from app.projects.models import Project
from app.projects.project_service import ProjectService


def _engine(tmp: Path) -> tuple[ProductionEngine, Project, PipelineContext]:
    data_root = tmp / "atlas"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    Storage(config).ensure_structure()
    projects = ProjectService(config)
    created = projects.create_project(channel, "Atlantis")
    engine = ProductionEngine(projects)
    context = engine.build_context(
        created,
        channel_defaults=ChannelDefaults(
            name=channel,
            image_prompt="cinematic",
        ),
    )
    return engine, created, context


class _SuccessPipeline(Pipeline):
    @property
    def pipeline_id(self) -> str:
        return "fake_success"

    @property
    def name(self) -> str:
        return "Fake Success"

    def run(self, context: PipelineContext) -> PipelineResult:
        target = context.folder("script") / "note.txt"
        target.write_text("ok", encoding="utf-8")
        self._set_progress(1.0, "Done")
        return PipelineResult.success("Wrote note", artifacts=["script/note.txt"])


class _FailPipeline(Pipeline):
    @property
    def pipeline_id(self) -> str:
        return "fake_fail"

    @property
    def name(self) -> str:
        return "Fake Fail"

    def run(self, context: PipelineContext) -> PipelineResult:
        return PipelineResult.failed("boom")


class _CancelPipeline(Pipeline):
    @property
    def pipeline_id(self) -> str:
        return "fake_cancel"

    @property
    def name(self) -> str:
        return "Fake Cancel"

    def run(self, context: PipelineContext) -> PipelineResult:
        self.cancel()
        return PipelineResult.success("should become cancelled")


class _InvalidPipeline(Pipeline):
    @property
    def pipeline_id(self) -> str:
        return "fake_invalid"

    @property
    def name(self) -> str:
        return "Fake Invalid"

    def validate(self, context: PipelineContext) -> list[str]:
        return ["missing input"]

    def run(self, context: PipelineContext) -> PipelineResult:
        return PipelineResult.success("should not run")


class ProductionEngineTests(unittest.TestCase):
    def test_success_refreshes_intelligence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, context = _engine(Path(tmp))
            result = engine.execute(_SuccessPipeline(), context)

            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertTrue(result.ok)
            self.assertIsNotNone(engine.last_progress)
            assert engine.last_progress is not None
            self.assertTrue(engine.last_progress.step("script").complete)  # type: ignore[union-attr]
            self.assertTrue((context.folder("script") / "note.txt").is_file())

    def test_failure_structured_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, context = _engine(Path(tmp))
            pipeline = _FailPipeline()
            result = engine.execute(pipeline, context)

            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertEqual(pipeline.status(), PipelineState.FAILED)
            self.assertFalse(result.ok)

    def test_cancel_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, context = _engine(Path(tmp))
            pipeline = _CancelPipeline()
            result = engine.execute(pipeline, context)

            self.assertEqual(result.outcome, PipelineOutcome.CANCELLED)
            self.assertEqual(pipeline.status(), PipelineState.CANCELLED)

    def test_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, context = _engine(Path(tmp))
            pipeline = _InvalidPipeline()
            result = engine.execute(pipeline, context)

            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertIn("missing input", result.errors)
            self.assertEqual(pipeline.status(), PipelineState.FAILED)

    def test_context_has_no_hardcoded_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, context = _engine(Path(tmp))
            self.assertTrue(context.project_dir.is_absolute())
            self.assertEqual(context.channel_defaults.image_prompt, "cinematic")
            script = context.folder("script")
            self.assertEqual(script.name, "script")
            self.assertTrue(str(script).startswith(str(context.project_dir)))

    def test_registry_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, context = _engine(Path(tmp))
            engine.registry.register("fake_success", _SuccessPipeline)
            result = engine.execute_registered("fake_success", context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)


class DependencyDirectionTests(unittest.TestCase):
    def test_channels_do_not_import_pipelines(self) -> None:
        channel_dir = Path(__file__).resolve().parents[1] / "app" / "channels"
        for path in channel_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("app.pipelines", source, msg=str(path))


if __name__ == "__main__":
    unittest.main()
