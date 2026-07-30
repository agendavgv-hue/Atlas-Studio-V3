"""ThumbnailService — central thumbnail orchestrator.

Coordinates selection → request prep → generation → export → manifest.
Contains no provider-specific logic (only ImageGenerationRequest + ImageProvider ABC).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.providers.errors import ProviderError
from app.providers.image_base import ImageGenerationRequest, ImageProvider
from app.thumbnail.exporter import ThumbnailExporter
from app.thumbnail.generator import ThumbnailGenerator
from app.thumbnail.manifest import ManifestGeneration, ManifestOutput, ThumbnailManifest
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.naming import (
    THUMBNAIL_BASENAME,
    THUMBNAIL_FOLDER,
    thumbnail_manifest_path,
)
from app.thumbnail.selector import SelectionDecision, ThumbnailSelector
from app.thumbnail.settings import ThumbnailSettings

ProgressCallback = Callable[[str, str], None]
# message, stage


class ThumbnailService:
    """Reusable thumbnail orchestration for long-form and future formats."""

    def __init__(
        self,
        settings: ThumbnailSettings,
        *,
        image_provider: ImageProvider | None = None,
        selector: ThumbnailSelector | None = None,
        generator: ThumbnailGenerator | None = None,
        exporter: ThumbnailExporter | None = None,
        on_progress: ProgressCallback | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self._settings = settings
        self._provider = image_provider
        self._selector = selector or ThumbnailSelector(settings)
        self._generator = generator or ThumbnailGenerator(image_provider)
        self._exporter = exporter or ThumbnailExporter()
        self._on_progress = on_progress
        self._cancel_check = cancel_check
        self._last_manifest: ThumbnailManifest | None = None
        self._last_decision: SelectionDecision | None = None

    @property
    def last_manifest(self) -> ThumbnailManifest | None:
        return self._last_manifest

    @property
    def last_decision(self) -> SelectionDecision | None:
        return self._last_decision

    def validate_ready(
        self,
        *,
        images: list[Path],
        thumbnail_prompt: str = "",
        project_title: str = "",
    ) -> list[str]:
        """Preflight checks before running (no I/O beyond provider validate)."""
        errors: list[str] = []
        mode = self._selector.select(
            images=images,
            thumbnail_prompt=thumbnail_prompt,
            project_title=project_title,
        ).mode
        if mode is ThumbnailMode.GENERATE:
            if self._provider is None:
                errors.append("No image provider is configured for thumbnail generation.")
            else:
                try:
                    self._provider.validate_ready()
                except ProviderError as exc:
                    errors.append(str(exc))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Image provider validation failed: {exc}")
            if not (thumbnail_prompt or "").strip() and not (project_title or "").strip():
                errors.append(
                    "No thumbnail prompt found. Set the channel thumbnail prompt "
                    "or use Select mode with project images."
                )
        else:
            if not images:
                errors.append("No images found. Generate Images before creating a thumbnail.")
        return errors

    def create_thumbnail(
        self,
        context: PipelineContext,
        *,
        images: list[Path],
        thumbnail_prompt: str = "",
        negative_prompt: str = "",
        project_title: str = "",
    ) -> PipelineResult:
        """Run the full thumbnail workflow for one project."""
        started = time.perf_counter()
        self._emit("Pipeline started", "started")

        if self._should_cancel():
            return PipelineResult.cancelled()

        self._emit("Images loaded", "images_loaded")
        decision = self._selector.select(
            images=images,
            thumbnail_prompt=thumbnail_prompt,
            negative_prompt=negative_prompt,
            project_title=project_title,
        )
        self._last_decision = decision
        self._emit("Thumbnail selected", "selected")

        if self._should_cancel():
            return PipelineResult.cancelled()

        request = self._build_generation_request(decision)
        try:
            generated = self._generator.generate(decision, request, context)
        except ProviderError as exc:
            return PipelineResult.failed(
                str(exc),
                errors=[str(exc)],
                execution_time_ms=self._elapsed_ms(started),
            )
        self._emit("Thumbnail generated", "generated")

        if self._should_cancel():
            return PipelineResult.cancelled()

        try:
            exported = self._exporter.export_png(context.project_dir, generated.image_png)
        except (ValueError, OSError) as exc:
            return PipelineResult.failed(
                f"Thumbnail export failed: {exc}",
                errors=[str(exc)],
                execution_time_ms=self._elapsed_ms(started),
            )

        final_path = exported.path
        if not final_path.is_file() or final_path.stat().st_size <= 0:
            return PipelineResult.failed(
                "Thumbnail export did not create thumbnail.png.",
                errors=["thumbnail.png is missing or empty"],
                execution_time_ms=self._elapsed_ms(started),
            )
        self._emit("Thumbnail exported", "exported")

        manifest = self._build_manifest(decision, generated.provider_id, request)
        manifest.exported = True
        manifest_path = thumbnail_manifest_path(context.project_dir)
        try:
            manifest.write_json(manifest_path)
            self._last_manifest = manifest
        except OSError as exc:
            return PipelineResult.failed(
                f"Failed to write thumbnail manifest: {exc}",
                errors=[str(exc)],
                execution_time_ms=self._elapsed_ms(started),
            )
        self._emit("Manifest written", "manifest")
        self._emit("Pipeline finished", "finished")

        artifacts = [
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{manifest_path.name}",
        ]
        return PipelineResult.success(
            f"Exported {THUMBNAIL_BASENAME} ({decision.mode.value})",
            artifacts=artifacts,
            execution_time_ms=self._elapsed_ms(started),
        )

    def _build_generation_request(
        self,
        decision: SelectionDecision,
    ) -> ImageGenerationRequest | None:
        if decision.mode is not ThumbnailMode.GENERATE:
            return None
        gen = decision.generation
        return ImageGenerationRequest(
            prompt=decision.prompt,
            negative_prompt=decision.negative_prompt,
            width=gen.width,
            height=gen.height,
            steps=gen.steps,
            cfg_scale=gen.cfg_scale,
            sampler=gen.sampler,
            seed=gen.seed,
            model=gen.model,
        )

    def _build_manifest(
        self,
        decision: SelectionDecision,
        provider_id: str,
        request: ImageGenerationRequest | None,
    ) -> ThumbnailManifest:
        generation = None
        if decision.mode is ThumbnailMode.GENERATE and request is not None:
            generation = ManifestGeneration(
                provider_id=provider_id,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                width=request.width,
                height=request.height,
                seed=request.seed,
                model=request.model,
                steps=request.steps,
                cfg_scale=request.cfg_scale,
                sampler=request.sampler,
            )
        return ThumbnailManifest(
            mode=decision.mode.value,
            source_image_path=(
                str(decision.source_image_path) if decision.source_image_path else None
            ),
            rationale=decision.rationale,
            output=ManifestOutput(
                folder=THUMBNAIL_FOLDER,
                filename=THUMBNAIL_BASENAME,
                width=decision.generation.width,
                height=decision.generation.height,
            ),
            generation=generation,
            exported=False,
        )

    def _should_cancel(self) -> bool:
        return self._cancel_check is not None and self._cancel_check()

    def _emit(self, message: str, stage: str) -> None:
        if self._on_progress is not None:
            self._on_progress(message, stage)

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)
