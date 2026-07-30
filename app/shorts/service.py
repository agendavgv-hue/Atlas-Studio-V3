"""ShortsService — central Shorts orchestrator.

Coordinates select → plan → manifest → generate/export each definition.
Contains no selection, planning, FFmpeg, or export implementation logic.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from app.core.movie_settings import RENDER_PROFILES, RenderProfileSpec
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.providers.errors import ProviderError
from app.render.ffmpeg import FFmpegProcess
from app.shorts.definition import ShortsDefinition
from app.shorts.exporter import ShortsExporter
from app.shorts.generator import ShortsGenerator
from app.shorts.manifest import ShortsManifest
from app.shorts.naming import SHORTS_FOLDER, shorts_manifest_path
from app.shorts.planner import ShortsPlanner
from app.shorts.selection import SceneSelection
from app.shorts.selector import ShortsSelector
from app.shorts.settings import ShortsSettings

ProgressCallback = Callable[[str, str], None]
# message, stage


class ShortsService:
    """Reusable Shorts orchestration for one or more definitions."""

    def __init__(
        self,
        settings: ShortsSettings,
        *,
        ffmpeg: FFmpegProcess | None = None,
        selector: ShortsSelector | None = None,
        planner: ShortsPlanner | None = None,
        generator: ShortsGenerator | None = None,
        exporter: ShortsExporter | None = None,
        on_progress: ProgressCallback | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self._settings = settings
        self._ffmpeg = ffmpeg or FFmpegProcess()
        self._selector = selector or ShortsSelector()
        self._planner = planner or ShortsPlanner(settings)
        self._generator = generator or ShortsGenerator(self._ffmpeg)
        self._exporter = exporter or ShortsExporter()
        self._on_progress = on_progress
        self._cancel_check = cancel_check
        self._last_manifest: ShortsManifest | None = None
        self._last_selection: SceneSelection | None = None

    @property
    def last_manifest(self) -> ShortsManifest | None:
        return self._last_manifest

    @property
    def last_selection(self) -> SceneSelection | None:
        return self._last_selection

    def validate_ready(self, *, images: list[Path]) -> list[str]:
        errors: list[str] = []
        if not images:
            errors.append("No images found. Generate Images before creating Shorts.")
        try:
            self._ffmpeg.validate()
        except ProviderError as exc:
            errors.append(str(exc))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"FFmpeg validation failed: {exc}")
        return errors

    def create_shorts(
        self,
        context: PipelineContext,
        *,
        images: list[Path],
        sheet_text: str | None = None,
        voice_path: Path | None = None,
    ) -> PipelineResult:
        """Run the full Shorts workflow for one project."""
        started = time.perf_counter()
        self._emit("Pipeline started", "started")

        if self._should_cancel():
            return PipelineResult.cancelled()

        self._emit("Assets loaded", "assets_loaded")
        selection = self._selector.select(images=images, sheet_text=sheet_text)
        self._last_selection = selection
        self._emit("Scenes selected", "scenes_selected")

        if selection.count == 0:
            return PipelineResult.failed(
                "No scenes available for Shorts.",
                errors=["Scene selection is empty."],
                execution_time_ms=self._elapsed_ms(started),
            )

        if self._should_cancel():
            return PipelineResult.cancelled()

        voice_duration = None
        if voice_path is not None and voice_path.is_file():
            voice_duration = self._ffmpeg.probe_duration(voice_path)

        definitions = self._planner.plan(
            selection,
            voice_path=voice_path,
            voice_duration_sec=voice_duration,
        )
        self._emit("Shorts planned", "planned")

        if not definitions:
            return PipelineResult.failed(
                "Shorts planner produced no definitions.",
                errors=["Planner returned an empty list."],
                execution_time_ms=self._elapsed_ms(started),
            )

        manifest = ShortsManifest.from_definitions(
            definitions,
            selection_source=selection.source,
            rationale=selection.rationale,
        )
        self._last_manifest = manifest
        self._emit("Manifest planned", "manifest_planned")

        if self._should_cancel():
            return PipelineResult.cancelled()

        profile = self._resolve_profile()
        artifacts: list[str] = []
        total = len(definitions)

        for position, definition in enumerate(definitions, start=1):
            if self._should_cancel():
                return PipelineResult.cancelled(
                    queue_current=position - 1,
                    queue_total=total,
                    artifacts=artifacts,
                )

            self._emit(
                f"Generating short {position} / {total}",
                "generated",
            )
            try:
                generated = self._generator.generate(definition, context, profile)
            except ProviderError as exc:
                return PipelineResult.failed(
                    str(exc),
                    errors=[str(exc)],
                    queue_current=position,
                    queue_total=total,
                    execution_time_ms=self._elapsed_ms(started),
                )

            if self._should_cancel():
                return PipelineResult.cancelled(
                    queue_current=position - 1,
                    queue_total=total,
                    artifacts=artifacts,
                )

            self._emit(
                f"Exporting short {position} / {total}",
                "exported",
            )
            try:
                exported = self._exporter.export(
                    context.project_dir,
                    definition,
                    generated.video_bytes,
                )
            except (ValueError, OSError) as exc:
                return PipelineResult.failed(
                    f"Short export failed: {exc}",
                    errors=[str(exc)],
                    queue_current=position,
                    queue_total=total,
                    execution_time_ms=self._elapsed_ms(started),
                )

            if not exported.path.is_file() or exported.path.stat().st_size <= 0:
                return PipelineResult.failed(
                    f"Short export did not create {exported.path.name}.",
                    errors=["Exported short is missing or empty"],
                    queue_current=position,
                    queue_total=total,
                    execution_time_ms=self._elapsed_ms(started),
                )

            self._mark_exported(definition, exported.path)
            artifacts.append(f"{SHORTS_FOLDER}/{exported.path.name}")

        self._emit("Writing shorts manifest", "manifest")
        try:
            manifest_path = shorts_manifest_path(context.project_dir)
            manifest.write_json(manifest_path)
            self._last_manifest = manifest
            artifacts.append(f"{SHORTS_FOLDER}/{manifest_path.name}")
        except OSError as exc:
            return PipelineResult.failed(
                f"Failed to write shorts manifest: {exc}",
                errors=[str(exc)],
                execution_time_ms=self._elapsed_ms(started),
            )

        self._emit("Pipeline finished", "finished")
        return PipelineResult.success(
            f"Exported {len(definitions)} short(s) ({selection.source})",
            artifacts=artifacts,
            queue_current=total,
            queue_total=total,
            succeeded_indexes=[item.index for item in definitions],
            execution_time_ms=self._elapsed_ms(started),
        )

    def _resolve_profile(self) -> RenderProfileSpec:
        base = RENDER_PROFILES.get(self._settings.profile) or RENDER_PROFILES["shorts"]
        return RenderProfileSpec(
            base.profile_id,
            base.label,
            max(16, int(self._settings.width)),
            max(16, int(self._settings.height)),
            max(1, int(self._settings.fps)),
            codec=self._settings.codec or base.codec,
            preset=self._settings.preset or base.preset,
            crf=max(0, int(self._settings.crf)),
        )

    @staticmethod
    def _mark_exported(definition: ShortsDefinition, path: Path) -> None:
        definition.exported = True
        definition.export_path = str(path)

    def _should_cancel(self) -> bool:
        return self._cancel_check is not None and self._cancel_check()

    def _emit(self, message: str, stage: str) -> None:
        if self._on_progress is not None:
            self._on_progress(message, stage)

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)
