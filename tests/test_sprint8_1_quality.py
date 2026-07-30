"""Unit tests for QualityController (Sprint 8.1 component 3)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.render.ffmpeg import FFmpegProcess, MediaProbe
from app.render.quality import QualityController


class _ProbeFFmpeg(FFmpegProcess):
    def __init__(self, probe: MediaProbe | None) -> None:
        super().__init__("")
        self._media = probe

    def resolve(self) -> Path:
        return Path("fake-ffmpeg")

    def probe_media(self, path: Path) -> MediaProbe | None:
        if not path.is_file():
            return None
        return self._media


class QualityControllerTests(unittest.TestCase):
    def test_missing_file_fails(self) -> None:
        qc = QualityController(_ProbeFFmpeg(None))
        report = qc.validate(
            Path("missing.mp4"),
            expected_width=1920,
            expected_height=1080,
            expected_fps=30,
        )
        self.assertFalse(report.passed)
        self.assertTrue(report.errors)

    def test_empty_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(b"")
            qc = QualityController(_ProbeFFmpeg(None))
            report = qc.validate(
                path,
                expected_width=1920,
                expected_height=1080,
                expected_fps=30,
            )
            self.assertFalse(report.passed)

    def test_passes_with_matching_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(b"data")
            probe = MediaProbe(
                duration_sec=9.0,
                width=1920,
                height=1080,
                fps=30.0,
                has_video=True,
                has_audio=True,
            )
            qc = QualityController(_ProbeFFmpeg(probe))
            report = qc.validate(
                path,
                expected_width=1920,
                expected_height=1080,
                expected_fps=30,
                expected_duration_sec=9.0,
                require_audio=True,
            )
            self.assertTrue(report.passed)
            self.assertEqual(report.errors, [])

    def test_no_video_stream_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(b"data")
            probe = MediaProbe(has_video=False, has_audio=True, width=1920, height=1080)
            qc = QualityController(_ProbeFFmpeg(probe))
            report = qc.validate(
                path,
                expected_width=1920,
                expected_height=1080,
                expected_fps=30,
            )
            self.assertFalse(report.passed)
            self.assertTrue(any("video stream" in err.casefold() for err in report.errors))

    def test_never_mutates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(b"original")
            before = path.read_bytes()
            qc = QualityController(
                _ProbeFFmpeg(MediaProbe(has_video=False, width=1, height=1))
            )
            qc.validate(path, expected_width=1920, expected_height=1080, expected_fps=30)
            self.assertEqual(path.read_bytes(), before)


class _FailingQuality(QualityController):
    def validate(self, video_path: Path, **kwargs):  # type: ignore[no-untyped-def, override]
        from app.render.quality import QualityReport

        return QualityReport(passed=False, errors=["forced QC failure"], checks={})


class RenderServiceQualityGateTests(unittest.TestCase):
    def test_qc_failure_leaves_video_on_disk(self) -> None:
        from app.core.movie_settings import MovieSettings
        from app.pipelines.results import PipelineOutcome
        from app.render.manifest import RenderManifest
        from app.render.naming import final_video_path, render_manifest_path
        from app.render.service import RenderService
        from tests.test_sprint8_movie_pipeline import FakeFFmpeg, _engine

        with tempfile.TemporaryDirectory() as tmp:
            ffmpeg = FakeFFmpeg()
            _engine_obj, context = _engine(Path(tmp), ffmpeg)
            del _engine_obj
            settings = MovieSettings(motion="none", default_duration_sec=3.0)
            service = RenderService(
                settings,
                ffmpeg,
                quality=_FailingQuality(ffmpeg),
            )
            images = sorted((context.project_dir / "images").glob("image_*.png"))
            timeline = service.build_timeline(
                images=images,
                sheet_text="",
                voice_path=None,
            )
            result = service.render_movie(context.project_dir, timeline)
            final = final_video_path(context.project_dir)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertTrue(final.is_file())
            self.assertIn("forced QC failure", result.errors)
            # Manifest still written so the produced render is documented.
            path = render_manifest_path(context.project_dir)
            self.assertTrue(path.is_file())
            loaded = RenderManifest.read_json(path)
            self.assertIsNotNone(loaded.quality)
            assert loaded.quality is not None
            self.assertFalse(loaded.quality.passed)


if __name__ == "__main__":
    unittest.main()
