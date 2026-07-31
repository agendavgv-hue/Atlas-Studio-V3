"""Tests for Thumbnail Quality Assurance Engine."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.pipelines.context import ChannelDefaults, PipelineContext
from app.pipelines.results import PipelineOutcome
from app.projects.models import Project
from app.providers.base import TextProvider
from app.providers.image_base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)
from app.thumbnail.quality import (
    QualityEvaluationContext,
    QualityEvaluator,
    QualityGate,
    RuleBasedQualityEvaluator,
    ThumbnailQualityHistory,
    ThumbnailQualityScore,
)
from app.thumbnail.naming import (
    thumbnail_history_path,
    thumbnail_path,
    thumbnail_quality_path,
)
from app.thumbnail.service import ThumbnailService
from app.thumbnail.settings import ThumbnailSettings


class _FakeImage(ImageProvider):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def provider_id(self) -> str:
        return "fake"

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self.calls += 1
        return ImageGenerationResponse(
            image_png=b"PNG-bytes",
            seed=request.seed if request.seed >= 0 else self.calls,
            model="fake",
            width=1280,
            height=720,
        )

    def list_models(self) -> list[str]:
        return ["fake"]

    def test_connection(self) -> str:
        return "ok"

    def validate_ready(self) -> None:
        return None


class _FakeText(TextProvider):
    @property
    def provider_id(self) -> str:
        return "fake-text"

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        del system
        lowered = (prompt or "").casefold()
        if "do not write an image prompt" in lowered or '"emotion": one of' in lowered:
            return json.dumps(
                {
                    "emotion": "Mystery",
                    "click_reason": "Impossible ancient tech.",
                    "hero_subject": "Baghdad Battery",
                    "dominant_feeling": "curiosity",
                    "rationale": "CTR",
                }
            )
        if "critique this thumbnail" in lowered or "rewritten_prompt" in lowered:
            return json.dumps(
                {
                    "passed": True,
                    "checks": {
                        "single_hero": True,
                        "simple_composition": True,
                        "supporting_background": True,
                        "readable_small": True,
                        "empty_headline_side": True,
                        "channel_recognizable": True,
                    },
                    "notes": "ok",
                    "rewritten_prompt": "",
                }
            )
        return json.dumps(
            {
                "hero_subject": "Baghdad Battery",
                "hook": "WHO BUILT THIS?",
                "rationale": "icon",
            }
        )


class _FailEvaluator(QualityEvaluator):
    @property
    def evaluator_id(self) -> str:
        return "fail_test"

    def evaluate(self, context: QualityEvaluationContext) -> ThumbnailQualityScore:
        del context
        return ThumbnailQualityScore(
            hero_subject=5,
            curiosity=5,
            composition=5,
            headline_space=5,
            impact=5,
            readability=5,
            dna=5,
            ctr=5,
            simplicity=5,
            professional=5,
            notes="forced fail",
            evaluator_id=self.evaluator_id,
        )


class _PassFromAttempt(QualityEvaluator):
    def __init__(self, pass_at: int = 2) -> None:
        self.pass_at = pass_at

    @property
    def evaluator_id(self) -> str:
        return "flaky_test"

    def evaluate(self, context: QualityEvaluationContext) -> ThumbnailQualityScore:
        if context.attempt >= self.pass_at:
            return ThumbnailQualityScore(
                hero_subject=10,
                curiosity=10,
                composition=10,
                headline_space=10,
                impact=10,
                readability=10,
                dna=10,
                ctr=10,
                simplicity=10,
                professional=10,
                notes="pass",
                evaluator_id=self.evaluator_id,
            )
        return ThumbnailQualityScore(
            hero_subject=4,
            curiosity=4,
            composition=4,
            headline_space=4,
            impact=4,
            readability=4,
            dna=4,
            ctr=4,
            simplicity=4,
            professional=4,
            notes="too early",
            evaluator_id=self.evaluator_id,
        )


def _context(tmp: Path) -> PipelineContext:
    project_dir = tmp / "Hollow Atlas" / "Baghdad Battery"
    project_dir.mkdir(parents=True)
    (project_dir / "script").mkdir()
    (project_dir / "script" / "script.txt").write_text(
        "The Baghdad Battery.", encoding="utf-8"
    )
    project = Project(
        name="Baghdad Battery",
        folder_name="Baghdad Battery",
        channel_name="Hollow Atlas",
    )
    return PipelineContext(
        project=project,
        project_dir=project_dir,
        channel_defaults=ChannelDefaults(name="Hollow Atlas"),
    )


class QualityModelsTests(unittest.TestCase):
    def test_score_sums_to_total(self) -> None:
        score = ThumbnailQualityScore(
            hero_subject=10,
            curiosity=9,
            composition=10,
            headline_space=10,
            impact=9,
            readability=9,
            dna=10,
            ctr=8,
            simplicity=8,
            professional=8,
        )
        self.assertEqual(score.score, 91)
        report = score.to_report(approved=True)
        self.assertTrue(report["approved"])
        self.assertEqual(report["score"], 91)
        self.assertEqual(report["impact"], 9)

    def test_rule_evaluator_scores_strong_package_high(self) -> None:
        ctx = QualityEvaluationContext(
            image_png=b"png",
            prompt=(
                "Professional YouTube thumbnail designed for maximum CTR, photorealistic. "
                "Emotion: Mystery. Single hero subject: Baghdad Battery. "
                "Channel DNA (Hollow Atlas). warm gold. clean simple composition. "
                "never busy. empty left headline. supporting background. "
                "high contrast. readable."
            ),
            negative_prompt="busy composition, watermark, logo",
            hero_subject="Baghdad Battery",
            hook="WHO BUILT THIS?",
            emotion="Mystery",
            click_reason="Impossible tech",
            channel_name="Hollow Atlas",
            channel_dna={
                "signature": "Hollow Atlas signature",
                "color_language": {"primary": "warm gold"},
            },
            critique={
                "checks": [
                    {"name": "single_hero", "passed": True},
                    {"name": "simple_composition", "passed": True},
                    {"name": "supporting_background", "passed": True},
                    {"name": "readable_small", "passed": True},
                    {"name": "empty_headline_side", "passed": True},
                    {"name": "channel_recognizable", "passed": True},
                ]
            },
        )
        score = RuleBasedQualityEvaluator().evaluate(ctx)
        gate = QualityGate(threshold=80)
        result = gate.assess(ctx)
        self.assertGreaterEqual(score.score, 80)
        self.assertTrue(result.approved)

    def test_gate_rejects_below_threshold(self) -> None:
        gate = QualityGate(_FailEvaluator(), threshold=80)
        result = gate.assess(
            QualityEvaluationContext(image_png=b"x", prompt="weak")
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.total, 50)
        self.assertIn("below threshold", result.rejection_reason.casefold())


class QualityServiceTests(unittest.TestCase):
    def test_approved_run_writes_quality_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _context(Path(tmp))
            images = _FakeImage()
            service = ThumbnailService(
                ThumbnailSettings(),
                image_provider=images,
                text_provider=_FakeText(),
            )
            result = service.create_thumbnail(
                context,
                script_text="The Baghdad Battery may have generated power.",
            )
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS, result.message)
            quality_path = thumbnail_quality_path(context.project_dir)
            self.assertTrue(quality_path.is_file())
            report = json.loads(quality_path.read_text(encoding="utf-8"))
            self.assertTrue(report["approved"])
            self.assertGreaterEqual(report["score"], 80)
            history = ThumbnailQualityHistory.read_json(
                thumbnail_history_path(context.project_dir)
            )
            self.assertGreaterEqual(len(history.entries), 1)
            self.assertTrue(history.entries[-1].approved)
            self.assertTrue(thumbnail_path(context.project_dir).is_file())
            self.assertEqual(images.calls, 4)

    def test_auto_reject_retries_until_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _context(Path(tmp))
            images = _FakeImage()
            service = ThumbnailService(
                ThumbnailSettings(max_quality_attempts=3),
                image_provider=images,
                text_provider=_FakeText(),
                quality_evaluator=_PassFromAttempt(pass_at=2),
            )
            result = service.create_thumbnail(
                context,
                script_text="The Baghdad Battery may have generated power.",
            )
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS, result.message)
            self.assertEqual(images.calls, 8)  # two attempts × 4 variants
            history = ThumbnailQualityHistory.read_json(
                thumbnail_history_path(context.project_dir)
            )
            self.assertEqual(len(history.entries), 2)
            self.assertFalse(history.entries[0].approved)
            self.assertTrue(history.entries[1].approved)
            self.assertIn("below threshold", history.entries[0].rejection_reason.casefold())

    def test_auto_reject_fails_after_max_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _context(Path(tmp))
            images = _FakeImage()
            service = ThumbnailService(
                ThumbnailSettings(max_quality_attempts=3),
                image_provider=images,
                text_provider=_FakeText(),
                quality_evaluator=_FailEvaluator(),
            )
            result = service.create_thumbnail(
                context,
                script_text="The Baghdad Battery may have generated power.",
            )
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertIn("QA failed", result.message)
            self.assertEqual(images.calls, 12)
            history = ThumbnailQualityHistory.read_json(
                thumbnail_history_path(context.project_dir)
            )
            self.assertEqual(len(history.entries), 3)
            self.assertTrue(all(not entry.approved for entry in history.entries))
            quality = json.loads(
                thumbnail_quality_path(context.project_dir).read_text(encoding="utf-8")
            )
            self.assertFalse(quality["approved"])
            self.assertFalse(thumbnail_path(context.project_dir).is_file())


if __name__ == "__main__":
    unittest.main()
