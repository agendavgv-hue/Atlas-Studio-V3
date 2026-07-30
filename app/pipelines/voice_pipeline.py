"""Voice pipeline — discover the script and drive the Voice Service."""

from __future__ import annotations

from collections.abc import Callable

from app.artifacts import ArtifactKind, ArtifactResolver
from app.artifacts.documents import read_document_text
from app.core.voice_settings import VoiceSettings
from app.pipelines.base import Pipeline
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.providers.voice_base import VoiceProvider
from app.voice.naming import resolve_voice_dir
from app.voice.service import VoiceService

# current, total, message, detail — preserved for TaskManager / VoiceWorker.
ProgressCallback = Callable[[int, int, str, str], None]


class VoicePipeline(Pipeline):
    """Professional voice production. Prefer ``generate_all`` (single complete file)."""

    def __init__(
        self,
        provider: VoiceProvider,
        settings: VoiceSettings | None = None,
        *,
        on_queue_progress: ProgressCallback | None = None,
    ) -> None:
        super().__init__()
        self._provider = provider
        self._settings = settings or _settings_from_provider(provider)
        self._on_queue_progress = on_queue_progress

    @property
    def pipeline_id(self) -> str:
        return "voice"

    @property
    def name(self) -> str:
        return "Voice"

    def validate(self, context: PipelineContext) -> list[str]:
        errors = super().validate(context)
        if errors:
            return errors

        script = ArtifactResolver(context.project_dir).find(ArtifactKind.SCRIPT)
        if script is None:
            errors.append("No script found. Generate Production first.")
            return errors
        try:
            text = read_document_text(script).strip()
        except OSError as exc:
            errors.append(f"Cannot read script: {exc}")
            return errors

        service = VoiceService(
            self._provider,
            self._settings,
            cancel_check=self.is_cancel_requested,
        )
        errors.extend(service.validate_ready(script_text=text))

        try:
            voice_dir = resolve_voice_dir(context.project_dir)
            if not voice_dir.is_dir():
                errors.append(f"Voice output folder is not available: {voice_dir}")
            else:
                probe = voice_dir / ".atlas_write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"Voice output folder is not writable: {exc}")

        return errors

    def run(self, context: PipelineContext) -> PipelineResult:
        return self.generate_all(context)

    def generate_all(self, context: PipelineContext) -> PipelineResult:
        """Discover the script and delegate narration production to VoiceService."""
        total = 1
        if self.is_cancel_requested():
            return PipelineResult.cancelled(queue_current=0, queue_total=total)

        script = ArtifactResolver(context.project_dir).find(ArtifactKind.SCRIPT)
        if script is None:
            return PipelineResult.failed("No script found.")

        try:
            text = read_document_text(script).strip()
        except OSError as exc:
            return PipelineResult.failed(f"Cannot read script: {exc}", errors=[str(exc)])
        if not text:
            return PipelineResult.failed("Script is empty — nothing to narrate.")

        preview = text if len(text) <= 80 else text[:77] + "…"

        def on_progress(message: str, stage: str) -> None:
            stage_progress = {
                "started": 0.05,
                "script_loaded": 0.15,
                "planned": 0.3,
                "manifest_ready": 0.4,
                "generated": 0.65,
                "exported": 0.85,
                "manifest": 0.95,
                "finished": 1.0,
            }
            self._set_progress(stage_progress.get(stage, 0.5), message)
            detail = preview if stage in {"script_loaded", "generated"} else script.name
            if stage in {"exported", "finished", "manifest"}:
                detail = "voice.wav"
            self._emit_queue(1, total, message, detail)

        service = VoiceService(
            self._provider,
            self._settings,
            on_progress=on_progress,
            cancel_check=self.is_cancel_requested,
        )
        return service.create_voice(context, script_text=text)

    def _emit_queue(self, current: int, total: int, message: str, detail: str = "") -> None:
        if self._on_queue_progress is not None:
            self._on_queue_progress(current, total, message, detail)


def _settings_from_provider(provider: VoiceProvider) -> VoiceSettings:
    settings = getattr(provider, "settings", None)
    if isinstance(settings, VoiceSettings):
        return settings
    return VoiceSettings()
