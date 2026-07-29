"""Movie pipeline — discover assets and drive the Render Service."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.artifacts import ArtifactKind, ArtifactResolver
from app.artifacts.documents import read_document_text
from app.core.movie_settings import MovieSettings
from app.pipelines.base import Pipeline
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.render.ffmpeg import FFmpegProcess
from app.render.naming import resolve_mp4_dir, resolve_youtube_dir
from app.render.service import RenderService

# current, total, message, stage, scene_label
ProgressCallback = Callable[[int, int, str, str, str], None]


class MoviePipeline(Pipeline):
    """Long-form YouTube movie. Prefer ``generate_all``."""

    def __init__(
        self,
        settings: MovieSettings,
        *,
        ffmpeg: FFmpegProcess | None = None,
        on_queue_progress: ProgressCallback | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._ffmpeg = ffmpeg or FFmpegProcess(settings.ffmpeg_path)
        self._on_queue_progress = on_queue_progress

    @property
    def pipeline_id(self) -> str:
        return "movie"

    @property
    def name(self) -> str:
        return "Movie"

    def cancel(self) -> None:
        super().cancel()
        self._ffmpeg.request_cancel()

    def validate(self, context: PipelineContext) -> list[str]:
        errors = super().validate(context)
        if errors:
            return errors

        resolver = ArtifactResolver(context.project_dir)
        images = resolver.find_all(ArtifactKind.IMAGES)
        if not images:
            errors.append("No images found. Generate Images before rendering a movie.")
            return errors

        service = RenderService(
            self._settings,
            self._ffmpeg,
            cancel_check=self.is_cancel_requested,
        )
        errors.extend(service.validate_ready())

        try:
            youtube_dir = resolve_youtube_dir(context.project_dir)
            probe = youtube_dir / ".atlas_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            resolve_mp4_dir(context.project_dir)
        except OSError as exc:
            errors.append(f"Movie output folder is not writable: {exc}")

        return errors

    def run(self, context: PipelineContext) -> PipelineResult:
        return self.generate_all(context)

    def generate_all(self, context: PipelineContext) -> PipelineResult:
        resolver = ArtifactResolver(context.project_dir)
        images = resolver.find_all(ArtifactKind.IMAGES)
        voice = resolver.find(ArtifactKind.VOICE)
        sheet = resolver.find(ArtifactKind.PRODUCTION_SHEET)
        sheet_text: str | None = None
        if sheet is not None:
            try:
                sheet_text = read_document_text(sheet)
            except OSError:
                sheet_text = None

        def on_progress(
            current: int,
            total: int,
            message: str,
            stage: str,
            scene_label: str,
        ) -> None:
            fraction = current / max(1, total)
            self._set_progress(fraction, message)
            if self._on_queue_progress is not None:
                self._on_queue_progress(current, total, message, stage, scene_label)

        service = RenderService(
            self._settings,
            self._ffmpeg,
            on_progress=on_progress,
            cancel_check=self.is_cancel_requested,
        )

        if self.is_cancel_requested():
            return PipelineResult.cancelled()

        self._set_progress(0.05, "Building timeline")
        on_progress(0, max(1, len(images)), "Building timeline", "timeline", "")

        seed = abs(hash(context.project_dir.name)) % (2**31)
        timeline = service.build_timeline(
            images=images,
            voice_path=voice,
            sheet_text=sheet_text,
            music_path=None,
            project_seed=seed,
        )

        if self.is_cancel_requested():
            return PipelineResult.cancelled()

        return service.render_movie(context.project_dir, timeline)
