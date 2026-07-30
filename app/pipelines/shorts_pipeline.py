"""Shorts pipeline — discover assets and drive the Shorts Service."""

from __future__ import annotations

from collections.abc import Callable

from app.artifacts import ArtifactKind, ArtifactResolver
from app.artifacts.documents import read_document_text
from app.pipelines.base import Pipeline
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.render.duration import natural_image_sort_key
from app.render.ffmpeg import FFmpegProcess
from app.shorts.naming import resolve_shorts_dir
from app.shorts.service import ShortsService
from app.shorts.settings import ShortsSettings

# message, stage
ProgressCallback = Callable[[str, str], None]


class ShortsPipeline(Pipeline):
    """YouTube Shorts production. Prefer ``generate_all``."""

    def __init__(
        self,
        settings: ShortsSettings | None = None,
        *,
        ffmpeg: FFmpegProcess | None = None,
        on_queue_progress: ProgressCallback | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings or ShortsSettings()
        self._ffmpeg = ffmpeg or FFmpegProcess()
        self._on_queue_progress = on_queue_progress

    @property
    def pipeline_id(self) -> str:
        return "shorts"

    @property
    def name(self) -> str:
        return "Shorts"

    def cancel(self) -> None:
        super().cancel()
        self._ffmpeg.request_cancel()

    def validate(self, context: PipelineContext) -> list[str]:
        errors = super().validate(context)
        if errors:
            return errors

        resolver = ArtifactResolver(context.project_dir)
        images = sorted(
            resolver.find_all(ArtifactKind.IMAGES),
            key=natural_image_sort_key,
        )
        service = ShortsService(
            self._settings,
            ffmpeg=self._ffmpeg,
            cancel_check=self.is_cancel_requested,
        )
        errors.extend(service.validate_ready(images=images))

        try:
            shorts_dir = resolve_shorts_dir(context.project_dir)
            probe = shorts_dir / ".atlas_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"Shorts output folder is not writable: {exc}")

        return errors

    def run(self, context: PipelineContext) -> PipelineResult:
        return self.generate_all(context)

    def generate_all(self, context: PipelineContext) -> PipelineResult:
        resolver = ArtifactResolver(context.project_dir)
        images = sorted(
            resolver.find_all(ArtifactKind.IMAGES),
            key=natural_image_sort_key,
        )
        voice = resolver.find(ArtifactKind.VOICE)
        sheet = resolver.find(ArtifactKind.PRODUCTION_SHEET)
        sheet_text: str | None = None
        if sheet is not None:
            try:
                sheet_text = read_document_text(sheet)
            except OSError:
                sheet_text = None

        def on_progress(message: str, stage: str) -> None:
            stage_progress = {
                "started": 0.05,
                "assets_loaded": 0.12,
                "scenes_selected": 0.25,
                "planned": 0.35,
                "manifest_planned": 0.4,
                "generated": 0.7,
                "exported": 0.85,
                "manifest": 0.95,
                "finished": 1.0,
            }
            self._set_progress(stage_progress.get(stage, 0.5), message)
            if self._on_queue_progress is not None:
                self._on_queue_progress(message, stage)

        service = ShortsService(
            self._settings,
            ffmpeg=self._ffmpeg,
            on_progress=on_progress,
            cancel_check=self.is_cancel_requested,
        )

        if self.is_cancel_requested():
            return PipelineResult.cancelled()

        return service.create_shorts(
            context,
            images=images,
            sheet_text=sheet_text,
            voice_path=voice,
        )
