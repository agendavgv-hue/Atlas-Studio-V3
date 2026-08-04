"""VoiceService — central Voice orchestrator.

Coordinates plan → manifest → generate → export → finalize manifest.
Contains no provider SDK logic, synthesis, or file-format invention.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from app.core.voice_settings import VoiceSettings
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.providers.errors import ProviderError
from app.providers.voice_base import VoiceProvider
from app.voice.exporter import VoiceExporter
from app.voice.generator import VoiceGenerator
from app.voice.manifest import VoiceManifest
from app.voice.naming import VOICE_BASENAME, VOICE_FOLDER, voice_manifest_path
from app.voice.plan import VoicePlan
from app.voice.planner import VoicePlanner

ProgressCallback = Callable[[str, str], None]
# message, stage


class VoiceService:
    """Reusable voice orchestration for one project narration."""

    def __init__(
        self,
        provider: VoiceProvider,
        settings: VoiceSettings | None = None,
        *,
        planner: VoicePlanner | None = None,
        generator: VoiceGenerator | None = None,
        exporter: VoiceExporter | None = None,
        on_progress: ProgressCallback | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings or VoiceSettings()
        self._planner = planner or VoicePlanner(self._settings)
        self._generator = generator or VoiceGenerator()
        self._exporter = exporter or VoiceExporter()
        self._on_progress = on_progress
        self._cancel_check = cancel_check
        self._last_manifest: VoiceManifest | None = None

    @property
    def last_manifest(self) -> VoiceManifest | None:
        return self._last_manifest

    def validate_ready(self, *, script_text: str) -> list[str]:
        """Preflight checks before running (provider readiness + script text)."""
        errors: list[str] = []
        if not (script_text or "").strip():
            errors.append("Script is empty — nothing to narrate.")
        try:
            self._provider.validate_ready()
        except ProviderError as exc:
            errors.append(str(exc))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Voice provider validation failed: {exc}")
        return errors

    def create_voice(
        self,
        context: PipelineContext,
        *,
        script_text: str,
    ) -> PipelineResult:
        """Run the full voice workflow for one project."""
        started = time.perf_counter()
        total = 1
        self._emit("Pipeline started", "started")

        if self._should_cancel():
            return PipelineResult.cancelled(queue_current=0, queue_total=total)

        text = str(script_text or "").strip()
        if not text:
            return PipelineResult.failed(
                "Script is empty — nothing to narrate.",
                errors=["Script is empty — nothing to narrate."],
                queue_current=0,
                queue_total=total,
                execution_time_ms=self._elapsed_ms(started),
            )

        self._emit("Reading script", "script_loaded")

        if self._should_cancel():
            return PipelineResult.cancelled(queue_current=0, queue_total=total)

        try:
            plan = self._planner.plan(text)
        except ValueError as exc:
            return PipelineResult.failed(
                str(exc),
                errors=[str(exc)],
                queue_current=0,
                queue_total=total,
                execution_time_ms=self._elapsed_ms(started),
            )
        self._emit("Voice planned", "planned")

        manifest = self._build_manifest(plan)
        self._last_manifest = manifest
        self._emit("Manifest ready", "manifest_ready")

        if self._should_cancel():
            return PipelineResult.cancelled(queue_current=0, queue_total=total)

        self._emit("Generating voice", "generated")
        try:
            generated = self._generator.generate(manifest, self._provider, context)
        except ProviderError as exc:
            return PipelineResult.failed(
                f"Voice generation failed: {exc}",
                errors=[str(exc)],
                queue_current=1,
                queue_total=total,
                execution_time_ms=self._elapsed_ms(started),
            )
        except Exception as exc:  # noqa: BLE001
            return PipelineResult.failed(
                f"Voice generation failed: {exc}",
                errors=[str(exc)],
                queue_current=1,
                queue_total=total,
                execution_time_ms=self._elapsed_ms(started),
            )

        self._emit("Saving voice", "exported")
        try:
            exported = self._exporter.export_wav(context.project_dir, generated.audio_bytes)
        except (ValueError, OSError) as exc:
            return PipelineResult.failed(
                f"Cannot write voice file: {exc}",
                errors=[str(exc)],
                queue_current=1,
                queue_total=total,
                execution_time_ms=self._elapsed_ms(started),
            )

        if not exported.path.is_file() or exported.path.stat().st_size <= 0:
            return PipelineResult.failed(
                f"Voice export did not create {VOICE_BASENAME}.",
                errors=[f"{VOICE_BASENAME} is missing or empty"],
                queue_current=1,
                queue_total=total,
                execution_time_ms=self._elapsed_ms(started),
            )

        artifact = f"{VOICE_FOLDER}/{VOICE_BASENAME}"
        if self._should_cancel():
            return PipelineResult.cancelled(
                "Cancelled after voice was generated",
                queue_current=1,
                queue_total=total,
                artifacts=[artifact],
                execution_time_ms=self._elapsed_ms(started),
            )

        manifest.exported = True
        self._emit("Writing voice manifest", "manifest")
        try:
            manifest_path = voice_manifest_path(context.project_dir)
            manifest.write_json(manifest_path)
            self._last_manifest = manifest
        except OSError as exc:
            return PipelineResult.failed(
                f"Failed to write voice manifest: {exc}",
                errors=[str(exc)],
                queue_current=1,
                queue_total=total,
                execution_time_ms=self._elapsed_ms(started),
            )

        artifacts = [
            artifact,
            f"{VOICE_FOLDER}/{manifest_path.name}",
        ]
        self._emit("Voice complete", "finished")
        return PipelineResult.success(
            "Generated voice narration",
            artifacts=artifacts,
            queue_current=1,
            queue_total=total,
            succeeded_indexes=[1],
            execution_time_ms=self._elapsed_ms(started),
        )

    def _build_manifest(self, plan: VoicePlan) -> VoiceManifest:
        settings = self._settings
        manifest = VoiceManifest.from_plan(
            plan,
            provider_id=self._provider.provider_id,
            voice_id=str(settings.voice_id or ""),
            voice_name=str(settings.voice_name or ""),
            model=str(settings.model or ""),
            speed=float(settings.speed or 1.0),
            pitch=0.0,
            stability=float(settings.stability or 0.0),
            style=float(settings.style or 0.0),
            similarity=float(settings.similarity or 0.0),
        )
        # Prefer settings language when the planner left a blank locale.
        if settings.language and not (manifest.language or "").strip():
            manifest.language = str(settings.language)
        elif settings.language:
            manifest.language = str(settings.language)
        reference = str(getattr(settings, "reference_audio_path", "") or "").strip()
        if reference:
            manifest.extras["reference_audio_path"] = reference
        return manifest

    def _should_cancel(self) -> bool:
        return self._cancel_check is not None and self._cancel_check()

    def _emit(self, message: str, stage: str) -> None:
        if self._on_progress is not None:
            self._on_progress(message, stage)

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)
