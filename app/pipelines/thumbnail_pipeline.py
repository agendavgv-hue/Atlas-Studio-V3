"""Thumbnail pipeline — discover script and drive the Intelligent Thumbnail Engine."""

from __future__ import annotations

from collections.abc import Callable

from app.artifacts import ArtifactKind, ArtifactResolver
from app.artifacts.documents import read_document_text
from app.core.app_config import AppConfig
from app.pipelines.base import Pipeline
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.providers.base import TextProvider
from app.providers.image_base import ImageProvider
from app.render.duration import natural_image_sort_key
from app.thumbnail.anti_ai import AntiAiRulesLoader
from app.thumbnail.dna_loader import ChannelDNALoader
from app.thumbnail.naming import resolve_thumbnail_dir
from app.thumbnail.service import ThumbnailService
from app.thumbnail.settings import ThumbnailSettings
from app.thumbnail.style_loader import ChannelStyleLoader

ProgressCallback = Callable[[str, str], None]


class ThumbnailPipeline(Pipeline):
    """YouTube thumbnail designer. Prefer ``generate_all``."""

    def __init__(
        self,
        settings: ThumbnailSettings | None = None,
        *,
        image_provider: ImageProvider | None = None,
        text_provider: TextProvider | None = None,
        style_loader: ChannelStyleLoader | None = None,
        dna_loader: ChannelDNALoader | None = None,
        anti_ai_loader: AntiAiRulesLoader | None = None,
        on_queue_progress: ProgressCallback | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings or ThumbnailSettings()
        self._image_provider = image_provider
        self._text_provider = text_provider
        self._style_loader = style_loader
        self._dna_loader = dna_loader
        self._anti_ai_loader = anti_ai_loader
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

        script_text = self._load_script(context)
        images = self._load_images(context)
        service = ThumbnailService(
            self._settings,
            image_provider=self._image_provider,
            text_provider=self._text_provider,
            style_loader=self._style_loader,
            dna_loader=self._dna_loader,
            anti_ai_loader=self._anti_ai_loader,
            cancel_check=self.is_cancel_requested,
        )
        errors.extend(service.validate_ready(script_text=script_text, images=images))

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
        script_text = self._load_script(context)
        images = self._load_images(context)

        def on_progress(message: str, stage: str) -> None:
            stage_progress = {
                "started": 0.03,
                "direct": 0.06,
                "strategy": 0.09,
                "analyze": 0.12,
                "hero": 0.15,
                "hook": 0.18,
                "dna": 0.21,
                "style": 0.24,
                "composition": 0.27,
                "prompts": 0.30,
                "prompt_quality": 0.32,
                "critique": 0.33,
                "critique_done": 0.35,
                "qa_attempt_1": 0.38,
                "qa_attempt_2": 0.40,
                "qa_attempt_3": 0.42,
                "variant_a": 0.48,
                "variant_b": 0.55,
                "variant_c": 0.62,
                "variant_d": 0.68,
                "critic": 0.72,
                "qa": 0.76,
                "qa_approved": 0.80,
                "qa_rejected": 0.78,
                "qa_retry": 0.79,
                "export": 0.86,
                "memory": 0.90,
                "manifest": 0.95,
                "finished": 1.0,
                "selected": 0.4,
            }
            self._set_progress(stage_progress.get(stage.casefold(), 0.5), message)
            if self._on_queue_progress is not None:
                self._on_queue_progress(message, stage)

        service = ThumbnailService(
            self._settings,
            image_provider=self._image_provider,
            text_provider=self._text_provider,
            style_loader=self._style_loader,
            dna_loader=self._dna_loader,
            anti_ai_loader=self._anti_ai_loader,
            on_progress=on_progress,
            cancel_check=self.is_cancel_requested,
        )

        if self.is_cancel_requested():
            return PipelineResult.cancelled()

        return service.create_thumbnail(
            context,
            script_text=script_text,
            images=images,
        )

    @staticmethod
    def _load_script(context: PipelineContext) -> str:
        script = ArtifactResolver(context.project_dir).find(ArtifactKind.SCRIPT)
        if script is None:
            return ""
        try:
            return read_document_text(script).strip()
        except OSError:
            return ""

    @staticmethod
    def _load_images(context: PipelineContext) -> list:
        return sorted(
            ArtifactResolver(context.project_dir).find_all(ArtifactKind.IMAGES),
            key=natural_image_sort_key,
        )


def style_loader_for_config(config: AppConfig | None) -> ChannelStyleLoader:
    if config is None:
        return ChannelStyleLoader()
    return ChannelStyleLoader(
        data_root=config.data_root,
        project_root=config.project_root,
    )


def dna_loader_for_config(config: AppConfig | None) -> ChannelDNALoader:
    if config is None:
        return ChannelDNALoader()
    return ChannelDNALoader(
        data_root=config.data_root,
        project_root=config.project_root,
    )


def anti_ai_loader_for_config(config: AppConfig | None) -> AntiAiRulesLoader:
    if config is None:
        return AntiAiRulesLoader()
    return AntiAiRulesLoader(
        data_root=config.data_root,
        project_root=config.project_root,
    )
