"""Unit tests for Render Manifest (Sprint 8.1 component 1)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.render.manifest import RenderManifest
from app.render.naming import FINAL_BASENAME, MANIFEST_BASENAME, render_manifest_path
from app.render.timeline import Timeline, TimelineScene, TimelineSegment


class RenderManifestTests(unittest.TestCase):
    def test_from_timeline_preserves_intro_main_outro(self) -> None:
        timeline = Timeline(
            segments=[
                TimelineSegment(kind="intro", scenes=[]),
                TimelineSegment(
                    kind="main",
                    scenes=[
                        TimelineScene(
                            index=1,
                            image_path=Path("images/image_01.png"),
                            duration_sec=3.0,
                            motion="zoom_in",
                            transition="fade",
                        )
                    ],
                ),
                TimelineSegment(kind="outro", scenes=[]),
            ],
            voice_path=Path("mp3/voice.mp3"),
            duration_source="voice_equal_split",
        )
        manifest = RenderManifest.from_timeline(
            timeline,
            profile_id="youtube_hd",
            width=1920,
            height=1080,
            fps=30,
            codec="libx264",
            preset="medium",
            crf=23,
            keep_scene_renders=False,
            voice_duration_sec=12.0,
        )
        kinds = [segment.kind for segment in manifest.segments]
        self.assertEqual(kinds, ["intro", "main", "outro"])
        self.assertEqual(len(manifest.main_scenes), 1)
        self.assertEqual(manifest.output.video_filename, FINAL_BASENAME)
        self.assertEqual(manifest.audio.voice_path, str(Path("mp3/voice.mp3")))
        self.assertEqual(manifest.branding.intro_path, None)
        self.assertEqual(manifest.main_scenes[0].camera, {})
        self.assertEqual(manifest.main_scenes[0].effects, [])

    def test_round_trip_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            timeline = Timeline(
                segments=[
                    TimelineSegment(
                        kind="main",
                        scenes=[
                            TimelineScene(
                                index=1,
                                image_path=root / "a.png",
                                duration_sec=2.5,
                                motion="none",
                            )
                        ],
                    )
                ],
                duration_source="default_per_image",
            )
            manifest = RenderManifest.from_timeline(
                timeline,
                profile_id="custom",
                width=1280,
                height=720,
                fps=24,
                codec="libx264",
                preset="fast",
                crf=20,
                keep_scene_renders=True,
            )
            path = render_manifest_path(root)
            manifest.write_json(path)
            self.assertEqual(path.name, MANIFEST_BASENAME)
            loaded = RenderManifest.read_json(path)
            self.assertEqual(loaded.render.width, 1280)
            self.assertEqual(loaded.main_scenes[0].duration_sec, 2.5)
            self.assertTrue(loaded.output.keep_scene_renders)

    def test_render_service_writes_manifest_with_quality(self) -> None:
        from app.core.movie_settings import MovieSettings
        from app.pipelines.results import PipelineOutcome
        from app.render.service import RenderService
        from tests.test_sprint8_movie_pipeline import FakeFFmpeg, _engine

        with tempfile.TemporaryDirectory() as tmp:
            ffmpeg = FakeFFmpeg(voice_duration=9.0)
            _engine_obj, context = _engine(Path(tmp), ffmpeg)
            del _engine_obj
            (context.project_dir / "mp3").mkdir(parents=True, exist_ok=True)
            voice = context.project_dir / "mp3" / "voice.mp3"
            voice.write_bytes(b"ID3")
            settings = MovieSettings(motion="none", default_duration_sec=3.0)
            service = RenderService(settings, ffmpeg)
            images = sorted((context.project_dir / "images").glob("image_*.png"))
            timeline = service.build_timeline(
                images=images,
                sheet_text="",
                voice_path=voice,
            )
            result = service.render_movie(context.project_dir, timeline)
            self.assertEqual(result.outcome, PipelineOutcome.SUCCESS)

            path = render_manifest_path(context.project_dir)
            self.assertTrue(path.is_file())
            loaded = RenderManifest.read_json(path)
            self.assertEqual(loaded.duration_source, "voice_equal_split")
            self.assertEqual(loaded.audio.voice_duration_sec, 9.0)
            self.assertEqual([s.kind for s in loaded.segments], ["intro", "main", "outro"])
            self.assertEqual(len(loaded.main_scenes), 3)
            self.assertEqual(loaded.render.profile, "youtube_hd")
            self.assertIsNotNone(loaded.quality)
            assert loaded.quality is not None
            self.assertTrue(loaded.quality.passed)
            self.assertIsNotNone(service.last_manifest)
            self.assertEqual(service.last_manifest.total_duration_sec, loaded.total_duration_sec)


if __name__ == "__main__":
    unittest.main()
