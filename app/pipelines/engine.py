"""ProductionEngine — heart of Atlas Studio production execution.

Coordinates pipelines, chaining, providers, intelligence refresh, and
structured results. Designed for future Job Queue, retries, and logging.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from app.core.app_config import AppConfig
from app.core.project_root import require_project_root
from app.core.voice_settings import VoiceSettings
from app.channels.voice_preferences import ChannelVoicePreferences
from app.pipelines.base import Pipeline
from app.pipelines.context import ChannelDefaults, PipelineContext
from app.pipelines.image_pipeline import ImagePipeline, ProgressCallback
from app.pipelines.movie_pipeline import MoviePipeline
from app.pipelines.movie_pipeline import ProgressCallback as MovieProgressCallback
from app.pipelines.production_sheet_pipeline import ProductionSheetPipeline
from app.pipelines.registry import PipelineRegistry
from app.pipelines.results import PipelineOutcome, PipelineResult
from app.pipelines.script_pipeline import ScriptPipeline
from app.pipelines.shorts_pipeline import ShortsPipeline
from app.pipelines.shorts_pipeline import ProgressCallback as ShortsProgressCallback
from app.pipelines.states import PipelineState
from app.pipelines.thumbnail_pipeline import ThumbnailPipeline
from app.pipelines.thumbnail_pipeline import ProgressCallback as ThumbnailProgressCallback
from app.pipelines.voice_pipeline import VoicePipeline
from app.pipelines.voice_pipeline import ProgressCallback as VoiceProgressCallback
from app.projects.models import Project
from app.projects.project_numbering import project_title
from app.projects.project_paths import ProjectPaths
from app.projects.project_service import ProjectService
from app.projects.project_status import ProjectProgress
from app.prompts.assembler import PromptAssembler
from app.providers.base import TextProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.image_base import ImageProvider
from app.providers.image_registry import ImageProviderRegistry
from app.providers.registry import ProviderRegistry
from app.providers.voice_base import VoiceProvider
from app.providers.voice_registry import VoiceProviderRegistry
from app.render.ffmpeg import FFmpegProcess
from app.shorts.settings import ShortsSettings
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.settings import ThumbnailSettings

QueueProgressCallback = ProgressCallback
VoiceQueueProgressCallback = VoiceProgressCallback
MovieQueueProgressCallback = MovieProgressCallback
ThumbnailQueueProgressCallback = ThumbnailProgressCallback
ShortsQueueProgressCallback = ShortsProgressCallback


class ProductionEngine:
    """Execute pipelines against a project with shared lifecycle handling."""

    def __init__(
        self,
        project_service: ProjectService,
        config: AppConfig,
        registry: PipelineRegistry | None = None,
        provider_registry: ProviderRegistry | None = None,
        image_provider_registry: ImageProviderRegistry | None = None,
        voice_provider_registry: VoiceProviderRegistry | None = None,
        *,
        text_provider: TextProvider | None = None,
        image_provider: ImageProvider | None = None,
        voice_provider: VoiceProvider | None = None,
        ffmpeg: FFmpegProcess | None = None,
        prompts: PromptAssembler | None = None,
    ) -> None:
        self._projects = project_service
        self._config = config
        self.registry = registry or PipelineRegistry()
        self._providers = provider_registry or ProviderRegistry(config)
        self._image_providers = image_provider_registry or ImageProviderRegistry(config)
        self._voice_providers = voice_provider_registry or VoiceProviderRegistry(config)
        self._text_provider_override = text_provider  # tests only
        self._image_provider_override = image_provider  # tests only
        self._voice_provider_override = voice_provider  # tests only
        self._ffmpeg_override = ffmpeg  # tests only
        self._prompts = prompts or PromptAssembler()
        self._last_progress: ProjectProgress | None = None
        self._active_pipeline: Pipeline | None = None
        self._register_defaults()

    @property
    def last_progress(self) -> ProjectProgress | None:
        return self._last_progress

    def build_context(
        self,
        project: Project,
        channel_defaults: ChannelDefaults | None = None,
    ) -> PipelineContext:
        root = require_project_root(self._projects.project_root)
        paths = ProjectPaths(root, project.channel_name)
        project_dir = paths.project_dir(project.folder_name)
        return PipelineContext(
            project=project,
            project_dir=project_dir,
            channel_defaults=channel_defaults or ChannelDefaults(name=project.channel_name),
        )

    def resolve_text_provider(self) -> TextProvider:
        if self._text_provider_override is not None:
            return self._text_provider_override
        return self._providers.require_text_provider()

    def resolve_image_provider(self) -> ImageProvider:
        if self._image_provider_override is not None:
            return self._image_provider_override
        return self._image_providers.require_image_provider()

    def resolve_voice_provider(self) -> VoiceProvider:
        if self._voice_provider_override is not None:
            return self._voice_provider_override
        return self._voice_providers.require_voice_provider()

    def resolve_voice_settings_for(self, context: PipelineContext) -> VoiceSettings:
        """Merge app voice settings with per-channel narrator preferences.

        If the preferred voice id is missing from the live catalogue, silently
        rematch by language / gender / style tags so generation does not fail.
        """
        from app.providers.voice_metadata import resolve_available_voice

        prefs = ChannelVoicePreferences.from_mapping(context.channel_defaults.voice)
        if prefs.is_empty():
            settings = self._config.voice
            gender = ""
            styles: list[str] = []
            language = settings.language
            provider_id = self._config.voice_provider
        else:
            settings = prefs.apply_to_settings(self._config.voice)
            gender = prefs.gender
            styles = list(prefs.style_tags)
            language = prefs.language or settings.language
            provider_id = prefs.provider or self._config.voice_provider

        try:
            provider = self._voice_providers.require_voice_provider(
                provider_id=provider_id,
                settings=settings,
            )
            voices = provider.list_voices()
        except Exception:  # noqa: BLE001
            return settings

        resolved, _warning = resolve_available_voice(
            voices,
            preferred_voice_id=settings.voice_id,
            gender=gender,
            style_tags=styles,
            language=language,
        )
        if resolved is None or resolved.voice_id == settings.voice_id:
            return settings
        return VoiceSettings(
            api_key=settings.api_key,
            voice_id=resolved.voice_id,
            voice_name=resolved.name,
            language=resolved.language or settings.language,
            model=settings.model,
            stability=settings.stability,
            style=settings.style,
            speed=settings.speed,
            similarity=settings.similarity,
            output_format=settings.output_format,
        )

    def resolve_voice_provider_for(self, context: PipelineContext) -> VoiceProvider:
        if self._voice_provider_override is not None:
            return self._voice_provider_override
        prefs = ChannelVoicePreferences.from_mapping(context.channel_defaults.voice)
        settings = self.resolve_voice_settings_for(context)
        provider_id = prefs.provider or self._config.voice_provider
        return self._voice_providers.require_voice_provider(
            provider_id=provider_id,
            settings=settings,
        )

    def request_cancel(self) -> None:
        """Cooperative cancel of the active pipeline (after current unit of work)."""
        active = self._active_pipeline
        if active is not None:
            active.cancel()

    def execute(self, pipeline: Pipeline, context: PipelineContext) -> PipelineResult:
        """Validate, run, refresh intelligence on success, return structured result."""
        started = time.perf_counter()
        self._active_pipeline = pipeline
        pipeline._cancel_requested = False
        pipeline._set_state(PipelineState.READY)
        pipeline._set_progress(0.0, "")
        pipeline._set_result(None)

        try:
            errors = pipeline.validate(context)
            if errors:
                result = PipelineResult.failed(
                    "Validation failed",
                    errors=errors,
                    execution_time_ms=self._elapsed_ms(started),
                )
                pipeline._set_state(PipelineState.FAILED)
                pipeline._set_result(result)
                return result

            if pipeline.is_cancel_requested():
                result = PipelineResult.cancelled(execution_time_ms=self._elapsed_ms(started))
                pipeline._set_state(PipelineState.CANCELLED)
                pipeline._set_result(result)
                return result

            pipeline._set_state(PipelineState.RUNNING)
            pipeline._set_progress(0.0, "Running")

            try:
                result = pipeline.run(context)
            except Exception as exc:  # noqa: BLE001 — boundary for all pipelines
                result = PipelineResult.failed(str(exc), errors=[str(exc)])

            if pipeline.is_cancel_requested() and result.outcome != PipelineOutcome.CANCELLED:
                result = PipelineResult.cancelled(result.message or "Cancelled")

            result.execution_time_ms = self._elapsed_ms(started)

            if result.outcome == PipelineOutcome.CANCELLED:
                pipeline._set_state(PipelineState.CANCELLED)
            elif result.outcome == PipelineOutcome.FAILED:
                pipeline._set_state(PipelineState.FAILED)
            else:
                pipeline._set_state(PipelineState.COMPLETED)

            pipeline._set_progress(result.progress, result.message)
            pipeline._set_result(result)

            if result.ok:
                self._refresh_intelligence(context)

            return result
        finally:
            if self._active_pipeline is pipeline:
                self._active_pipeline = None

    def execute_chain(
        self,
        pipelines: Sequence[Pipeline],
        context: PipelineContext,
    ) -> PipelineResult:
        """Run pipelines sequentially; stop on first non-ok result."""
        started = time.perf_counter()
        artifacts: list[str] = []
        last = PipelineResult.failed("No pipelines provided")

        for pipeline in pipelines:
            last = self.execute(pipeline, context)
            artifacts.extend(last.artifacts)
            if not last.ok:
                last.artifacts = list(dict.fromkeys(artifacts))
                last.execution_time_ms = self._elapsed_ms(started)
                return last

        return PipelineResult.success(
            "Production chain completed",
            artifacts=list(dict.fromkeys(artifacts)),
            execution_time_ms=self._elapsed_ms(started),
        )

    def generate_production(
        self,
        context: PipelineContext,
        *,
        topic: str | None = None,
    ) -> PipelineResult:
        """Primary text workflow: Script → Production Sheet."""
        try:
            provider = self.resolve_text_provider()
        except ProviderConfigurationError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])

        topic_value = self._resolve_topic(context, topic)
        script = ScriptPipeline(provider, self._prompts, topic=topic_value)
        sheet = ProductionSheetPipeline(provider, self._prompts)
        return self.execute_chain([script, sheet], context)

    def regenerate_script(
        self,
        context: PipelineContext,
        *,
        topic: str | None = None,
    ) -> PipelineResult:
        try:
            provider = self.resolve_text_provider()
        except ProviderConfigurationError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])
        topic_value = self._resolve_topic(context, topic)
        return self.execute(
            ScriptPipeline(provider, self._prompts, topic=topic_value),
            context,
        )

    def regenerate_production_sheet(self, context: PipelineContext) -> PipelineResult:
        try:
            provider = self.resolve_text_provider()
        except ProviderConfigurationError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])

        from app.artifacts import ArtifactKind, ArtifactResolver

        if not ArtifactResolver(context.project_dir).exists(ArtifactKind.SCRIPT):
            return self.generate_production(context)

        return self.execute(ProductionSheetPipeline(provider, self._prompts), context)

    def generate_images(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: QueueProgressCallback | None = None,
    ) -> PipelineResult:
        """Generate every image from the production sheet."""
        try:
            provider = self.resolve_image_provider()
        except ProviderConfigurationError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])
        pipeline = ImagePipeline(
            provider,
            self._prompts,
            global_negative=self._config.forge.negative_prompt,
            on_queue_progress=on_queue_progress,
        )
        return self.execute(pipeline, context)

    def regenerate_images(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: QueueProgressCallback | None = None,
    ) -> PipelineResult:
        return self.generate_images(context, on_queue_progress=on_queue_progress)

    def generate_image(
        self,
        context: PipelineContext,
        index: int,
        *,
        on_queue_progress: QueueProgressCallback | None = None,
    ) -> PipelineResult:
        """Regenerate a single 1-based image index (future Retry Failed / single regen)."""
        try:
            provider = self.resolve_image_provider()
        except ProviderConfigurationError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])
        pipeline = ImagePipeline(
            provider,
            self._prompts,
            global_negative=self._config.forge.negative_prompt,
            indexes=[index],
            on_queue_progress=on_queue_progress,
        )
        return self.execute(pipeline, context)

    def generate_voice(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: VoiceQueueProgressCallback | None = None,
    ) -> PipelineResult:
        """Generate one complete narration WAV via the Voice Service."""
        try:
            provider = self.resolve_voice_provider_for(context)
        except ProviderConfigurationError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])
        settings = self.resolve_voice_settings_for(context)
        pipeline = VoicePipeline(
            provider,
            settings,
            on_queue_progress=on_queue_progress,
        )
        return self.execute(pipeline, context)

    def regenerate_voice(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: VoiceQueueProgressCallback | None = None,
    ) -> PipelineResult:
        return self.generate_voice(context, on_queue_progress=on_queue_progress)

    def generate_movie(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: MovieQueueProgressCallback | None = None,
    ) -> PipelineResult:
        """Render the long-form YouTube movie via the Render Service."""
        ffmpeg = self._ffmpeg_override or FFmpegProcess(self._config.movie.ffmpeg_path)
        pipeline = MoviePipeline(
            self._config.movie,
            ffmpeg=ffmpeg,
            on_queue_progress=on_queue_progress,
        )
        return self.execute(pipeline, context)

    def regenerate_movie(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: MovieQueueProgressCallback | None = None,
    ) -> PipelineResult:
        return self.generate_movie(context, on_queue_progress=on_queue_progress)

    def generate_thumbnail(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: ThumbnailQueueProgressCallback | None = None,
        settings: ThumbnailSettings | None = None,
    ) -> PipelineResult:
        """Create the project thumbnail via the Thumbnail Service."""
        thumb_settings = settings or ThumbnailSettings()
        provider: ImageProvider | None = None
        mode = (thumb_settings.mode or ThumbnailMode.SELECT.value).strip().casefold()
        if mode == ThumbnailMode.GENERATE.value:
            try:
                provider = self.resolve_image_provider()
            except ProviderConfigurationError as exc:
                return PipelineResult.failed(str(exc), errors=[str(exc)])
        else:
            # Select/candidates do not require a provider; attach one when available.
            try:
                provider = self.resolve_image_provider()
            except ProviderConfigurationError:
                provider = None

        pipeline = ThumbnailPipeline(
            thumb_settings,
            image_provider=provider,
            on_queue_progress=on_queue_progress,
        )
        return self.execute(pipeline, context)

    def regenerate_thumbnail(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: ThumbnailQueueProgressCallback | None = None,
        settings: ThumbnailSettings | None = None,
    ) -> PipelineResult:
        return self.generate_thumbnail(
            context,
            on_queue_progress=on_queue_progress,
            settings=settings,
        )

    def generate_shorts(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: ShortsQueueProgressCallback | None = None,
        settings: ShortsSettings | None = None,
    ) -> PipelineResult:
        """Create YouTube Shorts via the Shorts Service."""
        ffmpeg = self._ffmpeg_override or FFmpegProcess(self._config.movie.ffmpeg_path)
        pipeline = ShortsPipeline(
            settings or ShortsSettings(),
            ffmpeg=ffmpeg,
            on_queue_progress=on_queue_progress,
        )
        return self.execute(pipeline, context)

    def regenerate_shorts(
        self,
        context: PipelineContext,
        *,
        on_queue_progress: ShortsQueueProgressCallback | None = None,
        settings: ShortsSettings | None = None,
    ) -> PipelineResult:
        return self.generate_shorts(
            context,
            on_queue_progress=on_queue_progress,
            settings=settings,
        )

    def execute_registered(
        self,
        pipeline_id: str,
        context: PipelineContext,
    ) -> PipelineResult:
        pipeline = self.registry.create(pipeline_id)
        return self.execute(pipeline, context)

    def _register_defaults(self) -> None:
        return

    def _refresh_intelligence(self, context: PipelineContext) -> None:
        self._last_progress = self._projects.get_progress(
            context.channel_name,
            context.project_name,
        )

    @staticmethod
    def _resolve_topic(context: PipelineContext, topic: str | None) -> str:
        if topic and topic.strip():
            return topic.strip()
        return project_title(context.project.name) or context.project.name.strip()

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)
