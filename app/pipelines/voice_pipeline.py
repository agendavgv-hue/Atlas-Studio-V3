"""Voice pipeline — Generate one complete narration MP3 from the project script."""

from __future__ import annotations

from collections.abc import Callable

from app.artifacts import ArtifactKind, ArtifactResolver
from app.artifacts.documents import read_document_text
from app.pipelines.base import Pipeline
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.pipelines.voice_naming import resolve_mp3_dir, voice_basename
from app.providers.errors import ProviderError
from app.providers.voice_base import VoiceProvider, VoiceSynthesisRequest

# current, total, message, detail
ProgressCallback = Callable[[int, int, str, str], None]


class VoicePipeline(Pipeline):
    """Professional voice production. Prefer ``generate_all`` (single complete file)."""

    def __init__(
        self,
        provider: VoiceProvider,
        *,
        on_queue_progress: ProgressCallback | None = None,
    ) -> None:
        super().__init__()
        self._provider = provider
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
        if not text:
            errors.append("Script is empty — nothing to narrate.")
            return errors

        try:
            self._provider.validate_ready()
        except ProviderError as exc:
            errors.append(str(exc))
            return errors
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Voice provider validation failed: {exc}")
            return errors

        try:
            mp3_dir = resolve_mp3_dir(context.project_dir)
            if not mp3_dir.is_dir():
                errors.append(f"Voice output folder is not available: {mp3_dir}")
            else:
                probe = mp3_dir / ".atlas_write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"Voice output folder is not writable: {exc}")

        return errors

    def run(self, context: PipelineContext) -> PipelineResult:
        return self.generate_all(context)

    def generate_all(self, context: PipelineContext) -> PipelineResult:
        """Synthesize the full script into one ``voice.mp3``."""
        total = 1
        if self.is_cancel_requested():
            return PipelineResult.cancelled(queue_current=0, queue_total=total)

        script = ArtifactResolver(context.project_dir).find(ArtifactKind.SCRIPT)
        if script is None:
            return PipelineResult.failed("No script found.")

        self._set_progress(0.15, "Reading script")
        self._emit_queue(1, total, "Reading script", script.name)
        try:
            text = read_document_text(script).strip()
        except OSError as exc:
            return PipelineResult.failed(f"Cannot read script: {exc}", errors=[str(exc)])
        if not text:
            return PipelineResult.failed("Script is empty — nothing to narrate.")

        if self.is_cancel_requested():
            return PipelineResult.cancelled(queue_current=0, queue_total=total)

        preview = text if len(text) <= 80 else text[:77] + "…"
        self._set_progress(0.4, "Generating voice")
        self._emit_queue(1, total, "Generating voice", preview)

        try:
            response = self._provider.synthesize(VoiceSynthesisRequest(text=text))
        except ProviderError as exc:
            return PipelineResult.failed(
                f"Voice generation failed: {exc}",
                errors=[str(exc)],
                queue_current=1,
                queue_total=total,
            )
        except Exception as exc:  # noqa: BLE001
            return PipelineResult.failed(
                f"Voice generation failed: {exc}",
                errors=[str(exc)],
                queue_current=1,
                queue_total=total,
            )

        # Cooperative cancel: current synthesis finishes, file is saved, then Cancelled.
        mp3_dir = resolve_mp3_dir(context.project_dir)
        out_path = mp3_dir / voice_basename(response.content_type)
        self._set_progress(0.85, "Saving voice")
        self._emit_queue(1, total, "Saving voice", out_path.name)
        try:
            out_path.write_bytes(response.audio_bytes)
        except OSError as exc:
            return PipelineResult.failed(
                f"Cannot write voice file: {exc}",
                errors=[str(exc)],
                queue_current=1,
                queue_total=total,
            )

        artifact = f"{mp3_dir.name}/{out_path.name}"
        if self.is_cancel_requested():
            return PipelineResult.cancelled(
                "Cancelled after voice was generated",
                queue_current=1,
                queue_total=total,
                artifacts=[artifact],
            )

        self._set_progress(1.0, "Voice complete")
        self._emit_queue(1, total, "Voice complete", out_path.name)
        return PipelineResult.success(
            "Generated voice narration",
            artifacts=[artifact],
            queue_current=1,
            queue_total=total,
            succeeded_indexes=[1],
        )

    def _emit_queue(self, current: int, total: int, message: str, detail: str = "") -> None:
        if self._on_queue_progress is not None:
            self._on_queue_progress(current, total, message, detail)
