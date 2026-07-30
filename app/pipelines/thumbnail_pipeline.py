"""Thumbnail pipeline — discover assets and drive the Thumbnail Service."""

from __future__ import annotations

from collections.abc import Callable

from app.artifacts import ArtifactKind, ArtifactResolver
from app.pipelines.base import Pipeline
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.providers.image_base import ImageProvider
from app.projects.project_numbering import project_title
from app.render.duration import natural_image_sort_key
from app.thumbnail.naming import resolve_thumbnail_dir
from app.thumbnail.service import ThumbnailService
from app.thumbnail.settings import ThumbnailSettings

# message, stage
ProgressCallback = Callable[[str, str], None]


class ThumbnailPipeline(Pipeline):
    """YouTube thumbnail production. Prefer ``generate_all``."""

    def __init__(
        self,
        settings: ThumbnailSettings | None = None,
        *,
        image_provider: ImageProvider | None = None,
        on_queue_progress: ProgressCallback | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings or ThumbnailSettings()
        self._image_provider = image_provider
        self._on_queue_progress = on_queue_progress

    @property
    def pipeline_id(self) -> str:
        return "thumbnail"

    @property
    def name(self) -> str:
        return "Thumbnail"

    def validate(self, context: PipelineContext) -> list[str]:
        errors = super().validate(context)
        if errors:
            return errors

        resolver = ArtifactResolver(context.project_dir)
        images = sorted(
            resolver.find_all(ArtifactKind.IMAGES),
            key=natural_image_sort_key,
        )
        prompt = (context.channel_defaults.thumbnail_prompt or "").strip()
        title = project_title(context.project.name) or context.project.name.strip()

        service = ThumbnailService(
            self._settings,
            image_provider=self._image_provider,
            cancel_check=self.is_cancel_requested,
        )
        errors.extend(
            service.validate_ready(
                images=images,
                thumbnail_prompt=prompt,
                project_title=title,
            )
        )

        try:
            thumb_dir = resolve_thumbnail_dir(context.project_dir)
            probe = thumb_dir / ".atlas_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"Thumbnail output folder is not writable: {exc}")

        return errors

    def run(self, context: PipelineContext) -> PipelineResult:
        return self.generate_all(context)

    def generate_all(self, context: PipelineContext) -> PipelineResult:
        resolver = ArtifactResolver(context.project_dir)
        images = sorted(
            resolver.find_all(ArtifactKind.IMAGES),
            key=natural_image_sort_key,
        )
        prompt = (context.channel_defaults.thumbnail_prompt or "").strip()
        negative = (context.channel_defaults.negative_prompt or "").strip()
        title = project_title(context.project.name) or context.project.name.strip()

        def on_progress(message: str, stage: str) -> None:
            stage_progress = {
                "started": 0.05,
                "images_loaded": 0.15,
                "selected": 0.35,
                "generated": 0.65,
                "exported": 0.85,
                "manifest": 0.95,
                "finished": 1.0,
            }
            self._set_progress(stage_progress.get(stage, 0.5), message)
            if self._on_queue_progress is not None:
                self._on_queue_progress(message, stage)

        service = ThumbnailService(
            self._settings,
            image_provider=self._image_provider,
            on_progress=on_progress,
            cancel_check=self.is_cancel_requested,
        )

        if self.is_cancel_requested():
            return PipelineResult.cancelled()

        return service.create_thumbnail(
            context,
            images=images,
            thumbnail_prompt=prompt,
            negative_prompt=negative,
            project_title=title,
        )
