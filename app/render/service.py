"""Render Service — central movie render orchestrator.

Coordinates timeline building, FFmpegRenderer execution, QC, manifest write,
cancel, and results. Does not embed FFmpeg argv construction (see ``FFmpegRenderer``).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from app.core.movie_settings import MovieSettings, RenderProfileSpec
from app.pipelines.results import PipelineResult
from app.providers.errors import ProviderError
from app.render.duration import natural_image_sort_key, resolve_scene_durations
from app.render.ffmpeg import FFmpegProcess
from app.render.motion import resolve_motion
from app.render.naming import (
    final_video_path,
    render_manifest_path,
    resolve_mp4_dir,
    resolve_work_dir,
    resolve_youtube_dir,
    scene_basename,
)
from app.render.manifest import ManifestQuality, RenderManifest
from app.render.quality import QualityController, QualityReport
from app.render.renderer import FFmpegRenderer
from app.render.timeline import Timeline, TimelineScene, TimelineSegment

ProgressCallback = Callable[[int, int, str, str, str], None]
# current, total, message, stage, scene_label


class RenderService:
    """Reusable render orchestration for long-form and future vertical formats."""

    def __init__(
        self,
        settings: MovieSettings,
        ffmpeg: FFmpegProcess | None = None,
        *,
        on_progress: ProgressCallback | None = None,
        cancel_check: Callable[[], bool] | None = None,
        renderer: FFmpegRenderer | None = None,
        quality: QualityController | None = None,
    ) -> None:
        self._settings = settings
        self._ffmpeg = ffmpeg or FFmpegProcess(settings.ffmpeg_path)
        self._renderer = renderer or FFmpegRenderer(self._ffmpeg)
        self._quality = quality or QualityController(self._ffmpeg)
        self._on_progress = on_progress
        self._cancel_check = cancel_check
        self._last_quality: QualityReport | None = None
        self._last_manifest: RenderManifest | None = None

    @property
    def ffmpeg(self) -> FFmpegProcess:
        return self._ffmpeg

    @property
    def renderer(self) -> FFmpegRenderer:
        return self._renderer

    @property
    def last_quality_report(self) -> QualityReport | None:
        return self._last_quality

    @property
    def last_manifest(self) -> RenderManifest | None:
        return self._last_manifest

    def validate_ready(self) -> list[str]:
        errors: list[str] = []
        try:
            self._ffmpeg.validate()
        except ProviderError as exc:
            errors.append(str(exc))
        return errors

    def build_timeline(
        self,
        *,
        images: list[Path],
        voice_path: Path | None,
        sheet_text: str | None,
        music_path: Path | None = None,
        project_seed: int = 0,
    ) -> Timeline:
        ordered = sorted(images, key=natural_image_sort_key)
        voice_duration = None
        if voice_path is not None and voice_path.is_file():
            voice_duration = self._ffmpeg.probe_duration(voice_path)

        durations, source = resolve_scene_durations(
            image_count=len(ordered),
            sheet_text=sheet_text,
            voice_duration_sec=voice_duration,
            default_duration_sec=self._settings.default_duration_sec,
        )

        transition = self._settings.transition
        scenes: list[TimelineScene] = []
        for index, path in enumerate(ordered, start=1):
            motion = resolve_motion(
                self._settings.motion,
                index=index,
                seed=project_seed,
            )
            scenes.append(
                TimelineScene(
                    index=index,
                    image_path=path,
                    duration_sec=durations[index - 1],
                    motion=motion,
                    transition=transition,
                )
            )

        # Intro / Outro reserved — empty until branding assets are wired.
        return Timeline(
            segments=[
                TimelineSegment(kind="intro", scenes=[]),
                TimelineSegment(kind="main", scenes=scenes),
                TimelineSegment(kind="outro", scenes=[]),
            ],
            voice_path=voice_path if voice_path and voice_path.is_file() else None,
            music_path=music_path,  # reserved
            duration_source=source,
        )

    def render_movie(self, project_dir: Path, timeline: Timeline) -> PipelineResult:
        """Render main timeline → optional scene files → youtube_video/video.mp4."""
        self._ffmpeg.reset_cancel()
        profile = self._settings.resolved_profile()
        scenes = timeline.main_scenes
        if not scenes:
            return PipelineResult.failed("No scenes to render.")

        youtube_dir = resolve_youtube_dir(project_dir)
        work_root = (
            resolve_mp4_dir(project_dir)
            if self._settings.keep_scene_renders
            else resolve_work_dir(project_dir)
        )
        started = time.perf_counter()
        artifacts: list[str] = []
        scene_files: list[Path] = []
        total = len(scenes)

        for position, scene in enumerate(scenes, start=1):
            if self._should_cancel():
                self._ffmpeg.request_cancel()
                return PipelineResult.cancelled(
                    queue_current=position - 1,
                    queue_total=total,
                    artifacts=artifacts,
                )

            message = f"Rendering Scene {position} / {total}"
            self._emit(position, total, message, "scene", scene.image_path.name)
            out = work_root / scene_basename(scene.index)
            try:
                self._renderer.render_scene(scene, out, profile)
            except ProviderError as exc:
                if self._should_cancel() or "cancelled" in str(exc).casefold():
                    return PipelineResult.cancelled(
                        queue_current=position,
                        queue_total=total,
                        artifacts=artifacts,
                    )
                return PipelineResult.failed(
                    f"Scene {scene.index} failed: {exc}",
                    errors=[str(exc)],
                    queue_current=position,
                    queue_total=total,
                )
            scene_files.append(out)
            if self._settings.keep_scene_renders:
                artifacts.append(f"{out.parent.name}/{out.name}")

        if self._should_cancel():
            return PipelineResult.cancelled(
                queue_current=total,
                queue_total=total,
                artifacts=artifacts,
            )

        final_path = final_video_path(project_dir)
        self._emit(total, total, "Exporting final video", "export", final_path.name)
        try:
            self._renderer.export_final(
                scene_files,
                timeline.voice_path,
                final_path,
                profile,
            )
        except ProviderError as exc:
            if self._should_cancel() or "cancelled" in str(exc).casefold():
                return PipelineResult.cancelled(
                    queue_current=total,
                    queue_total=total,
                    artifacts=artifacts,
                )
            return PipelineResult.failed(
                f"Export failed: {exc}",
                errors=[str(exc)],
                queue_current=total,
                queue_total=total,
            )

        artifacts.append(f"{youtube_dir.name}/{final_path.name}")

        self._emit(total, total, "Quality check", "qc", final_path.name)
        report = self._quality.validate(
            final_path,
            expected_width=profile.width,
            expected_height=profile.height,
            expected_fps=profile.fps,
            expected_duration_sec=timeline.total_duration_sec,
            require_audio=timeline.voice_path is not None,
        )
        self._last_quality = report

        # Manifest describes the produced render + QC result (sidecar only).
        self._emit(total, total, "Writing render manifest", "manifest", "")
        manifest = self._build_manifest(timeline, profile, report)
        manifest_path = render_manifest_path(project_dir)
        try:
            manifest.write_json(manifest_path)
            self._last_manifest = manifest
            artifacts.append(f"{youtube_dir.name}/{manifest_path.name}")
        except OSError as exc:
            if not report.passed:
                return PipelineResult.failed(
                    "Quality check failed",
                    errors=list(report.errors) or ["Quality check failed"],
                    queue_current=total,
                    queue_total=total,
                )
            return PipelineResult.failed(
                f"Failed to write render manifest: {exc}",
                errors=[str(exc)],
                queue_current=total,
                queue_total=total,
            )

        if not report.passed:
            # Video + manifest left on disk — QC never deletes or repairs.
            return PipelineResult.failed(
                "Quality check failed",
                errors=list(report.errors) or ["Quality check failed"],
                queue_current=total,
                queue_total=total,
            )

        if not self._settings.keep_scene_renders:
            self._cleanup_work(work_root)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        # Soft QC warnings do not change the SUCCESS outcome (backward compatible).
        # Callers can inspect ``last_quality_report`` for warnings/errors detail.
        return PipelineResult.success(
            f"Exported {final_path.name} ({timeline.duration_source}, "
            f"{total} scene(s), {timeline.total_duration_sec:.1f}s)",
            artifacts=artifacts,
            queue_current=total,
            queue_total=total,
            succeeded_indexes=[scene.index for scene in scenes],
            execution_time_ms=elapsed_ms,
        )

    def _build_manifest(
        self,
        timeline: Timeline,
        profile: RenderProfileSpec,
        report: QualityReport,
    ) -> RenderManifest:
        voice_duration = None
        if timeline.voice_path is not None and timeline.voice_path.is_file():
            voice_duration = self._ffmpeg.probe_duration(timeline.voice_path)
        manifest = RenderManifest.from_timeline(
            timeline,
            profile_id=profile.profile_id,
            width=profile.width,
            height=profile.height,
            fps=profile.fps,
            codec=profile.codec,
            preset=profile.preset,
            crf=profile.crf,
            keep_scene_renders=self._settings.keep_scene_renders,
            voice_duration_sec=voice_duration,
            music_enabled=self._settings.music_enabled,
            music_volume=self._settings.music_volume,
        )
        manifest.quality = ManifestQuality(
            passed=report.passed,
            warnings=list(report.warnings),
            errors=list(report.errors),
            checks=dict(report.checks),
        )
        return manifest

    def _cleanup_work(self, work_root: Path) -> None:
        if work_root.name != ".atlas_render":
            return
        try:
            for path in work_root.glob("scene_*.mp4"):
                path.unlink(missing_ok=True)
        except OSError:
            pass

    def _should_cancel(self) -> bool:
        if self._ffmpeg.is_cancel_requested():
            return True
        if self._cancel_check is not None and self._cancel_check():
            return True
        return False

    def _emit(
        self,
        current: int,
        total: int,
        message: str,
        stage: str,
        scene_label: str = "",
    ) -> None:
        if self._on_progress is not None:
            self._on_progress(current, total, message, stage, scene_label)
