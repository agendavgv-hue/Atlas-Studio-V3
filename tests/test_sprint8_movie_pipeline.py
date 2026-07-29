"""Sprint 8 — Movie Pipeline / Render Service tests (fake FFmpeg only)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from app.core.app_config import AppConfig
from app.core.movie_settings import MovieSettings
from app.core.storage import Storage
from app.pipelines.context import ChannelDefaults
from app.pipelines.engine import ProductionEngine
from app.pipelines.results import PipelineOutcome
from app.projects.project_service import ProjectService
from app.render.duration import extract_sheet_durations, resolve_scene_durations
from app.render.ffmpeg import FFmpegProcess
from app.render.motion import resolve_motion
from app.render.naming import final_video_path, scene_basename
from app.render.service import RenderService
from app.render.timeline import Timeline


class FakeFFmpeg(FFmpegProcess):
    """Test double — writes tiny files instead of invoking FFmpeg."""

    def __init__(self, *, voice_duration: float = 12.0) -> None:
        super().__init__("")
        self.voice_duration = voice_duration
        self.calls: list[list[str]] = []
        self._cancel_after_scenes: int | None = None
        self._scene_runs = 0

    def resolve(self) -> Path:
        return Path("fake-ffmpeg")

    def validate(self) -> str:
        return "Fake FFmpeg OK"

    def probe_duration(self, path: Path) -> float | None:
        if path.suffix.casefold() in {".mp3", ".wav", ".m4a"}:
            return self.voice_duration
        return 1.0

    def run(self, args: list[str], *, timeout: float | None = 3600) -> subprocess.CompletedProcess[str]:
        from app.providers.errors import ProviderError

        self.calls.append(list(args))
        out = Path(args[-1])
        if "-an" in args:
            self._scene_runs += 1
            if (
                self._cancel_after_scenes is not None
                and self._scene_runs >= self._cancel_after_scenes
            ):
                self.request_cancel()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00\x00fake-mp4")
        if self.is_cancel_requested():
            raise ProviderError("FFmpeg cancelled.")
        return subprocess.CompletedProcess(["fake-ffmpeg", *args], 0, "", "")


def _engine(tmp: Path, ffmpeg: FakeFFmpeg, **movie_kwargs) -> tuple[ProductionEngine, object]:
    data_root = tmp / "atlas"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    config.movie = MovieSettings.from_mapping(
        {
            "profile": "youtube_hd",
            "motion": "none",
            "transition": "cut",
            "default_duration_sec": 3.0,
            "keep_scene_renders": False,
            **movie_kwargs,
        }
    )
    Storage(config).ensure_structure()
    projects = ProjectService(config)
    project = projects.create_project(channel, "Atlantis")
    engine = ProductionEngine(projects, config, ffmpeg=ffmpeg)
    context = engine.build_context(project, channel_defaults=ChannelDefaults(name=channel))
    images = context.folder("images")
    images.mkdir(parents=True, exist_ok=True)
    (images / "image_01.png").write_bytes(b"png1")
    (images / "image_02.png").write_bytes(b"png2")
    (images / "image_03.png").write_bytes(b"png3")
    return engine, context


class DurationResolverTests(unittest.TestCase):
    def test_sheet_durations_preferred(self) -> None:
        sheet = """
IMAGE 01
Duration: 5
IMAGE 02
Duration: 7.5
IMAGE 03
Duration: 2
"""
        durations, source = resolve_scene_durations(
            image_count=3,
            sheet_text=sheet,
            voice_duration_sec=30.0,
            default_duration_sec=4.0,
        )
        self.assertEqual(source, "production_sheet")
        self.assertEqual(durations, [5.0, 7.5, 2.0])

    def test_voice_equal_split_fallback(self) -> None:
        durations, source = resolve_scene_durations(
            image_count=3,
            sheet_text="",
            voice_duration_sec=15.0,
            default_duration_sec=4.0,
        )
        self.assertEqual(source, "voice_equal_split")
        self.assertEqual(durations, [5.0, 5.0, 5.0])

    def test_default_per_image_fallback(self) -> None:
        durations, source = resolve_scene_durations(
            image_count=2,
            sheet_text=None,
            voice_duration_sec=None,
            default_duration_sec=4.0,
        )
        self.assertEqual(source, "default_per_image")
        self.assertEqual(durations, [4.0, 4.0])

    def test_incomplete_sheet_falls_through(self) -> None:
        sheet = "IMAGE 01\nDuration: 5\nIMAGE 02\n"
        self.assertIsNone(extract_sheet_durations(sheet, 2))


class MotionTests(unittest.TestCase):
    def test_random_is_stable_per_index(self) -> None:
        a = resolve_motion("random", index=1, seed=42)
        b = resolve_motion("random", index=1, seed=42)
        c = resolve_motion("random", index=2, seed=42)
        self.assertEqual(a, b)
        self.assertIn(a, {"zoom_in", "zoom_out", "pan_left", "pan_right", "none"})
        # Different index may differ; at least ensure concrete.
        self.assertIn(c, {"zoom_in", "zoom_out", "pan_left", "pan_right", "none"})


class MoviePipelineTests(unittest.TestCase):
    def test_exports_final_video_without_keeping_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg()
            engine, context = _engine(Path(tmp), fake)
            seen: list[tuple[int, int, str, str]] = []

            result = engine.generate_movie(
                context,
                on_queue_progress=lambda c, t, m, s="", l="": seen.append((c, t, m, s)),
            )

            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            final = final_video_path(context.project_dir)
            self.assertTrue(final.is_file())
            self.assertFalse((context.folder("mp4") / scene_basename(1)).is_file())
            self.assertTrue(any(item[2].startswith("Rendering Scene") for item in seen))

            progress = engine._projects.get_progress(
                context.channel_name,
                context.project_name,
            )
            self.assertTrue(progress.step("movie").complete)
            self.assertTrue(progress.step("youtube_export").complete)

    def test_keep_scene_renders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg()
            engine, context = _engine(Path(tmp), fake, keep_scene_renders=True)
            result = engine.generate_movie(context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertTrue((context.folder("mp4") / scene_basename(1)).is_file())
            self.assertTrue((context.folder("mp4") / scene_basename(3)).is_file())
            self.assertTrue(final_video_path(context.project_dir).is_file())

    def test_voice_optional_uses_default_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg()
            engine, context = _engine(Path(tmp), fake)
            result = engine.generate_movie(context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertIn("default_per_image", result.message)

    def test_voice_syncs_duration_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg(voice_duration=9.0)
            engine, context = _engine(Path(tmp), fake)
            (context.folder("mp3") / "voice.mp3").write_bytes(b"ID3")
            result = engine.generate_movie(context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertIn("voice_equal_split", result.message)

    def test_sheet_timing_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg()
            engine, context = _engine(Path(tmp), fake)
            sheet = context.folder("script") / "production_sheet.txt"
            sheet.write_text(
                "IMAGE 01\nDuration: 2\nIMAGE 02\nDuration: 3\nIMAGE 03\nDuration: 4\n",
                encoding="utf-8",
            )
            result = engine.generate_movie(context)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)
            self.assertIn("production_sheet", result.message)

    def test_missing_images_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg()
            engine, context = _engine(Path(tmp), fake)
            for path in context.folder("images").glob("*"):
                path.unlink()
            result = engine.generate_movie(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertTrue(any("image" in err.casefold() for err in result.errors))

    def test_missing_ffmpeg_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            class BrokenFFmpeg(FakeFFmpeg):
                def validate(self) -> str:
                    from app.providers.errors import ProviderError

                    raise ProviderError("FFmpeg was not found.")

            engine, context = _engine(Path(tmp), BrokenFFmpeg())
            result = engine.generate_movie(context)
            self.assertEqual(result.outcome, PipelineOutcome.FAILED)
            self.assertTrue(any("ffmpeg" in err.casefold() for err in result.errors))

    def test_cancel_stops_before_next_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg()
            fake._cancel_after_scenes = 1
            engine, context = _engine(Path(tmp), fake, keep_scene_renders=True)
            result = engine.generate_movie(context)
            self.assertEqual(result.outcome, PipelineOutcome.CANCELLED)
            self.assertTrue((context.folder("mp4") / scene_basename(1)).is_file())
            self.assertFalse(final_video_path(context.project_dir).is_file())
            self.assertFalse((context.folder("mp4") / scene_basename(2)).is_file())

    def test_timeline_has_intro_main_outro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeFFmpeg()
            settings = MovieSettings(motion="none", default_duration_sec=2.0)
            service = RenderService(settings, fake)
            root = Path(tmp)
            images = [root / "a.png", root / "b.png"]
            for path in images:
                path.write_bytes(b"x")
            timeline = service.build_timeline(
                images=images,
                voice_path=None,
                sheet_text=None,
                project_seed=1,
            )
            self.assertIsInstance(timeline, Timeline)
            kinds = [segment.kind for segment in timeline.segments]
            self.assertEqual(kinds, ["intro", "main", "outro"])
            self.assertEqual(len(timeline.main_scenes), 2)
            self.assertEqual(timeline.segments[0].scenes, [])
            self.assertEqual(timeline.segments[2].scenes, [])
            self.assertIsNone(timeline.music_path)


if __name__ == "__main__":
    unittest.main()
