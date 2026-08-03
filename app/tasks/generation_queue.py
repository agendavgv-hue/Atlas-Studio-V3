"""One-click production queue — chains existing TaskManager jobs.

Does not alter pipelines, services, contracts, or the manifest system.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from app.core.atlas_log import AtlasLog
from app.pipelines.results import PipelineOutcome, PipelineResult
from app.tasks.task_manager import TaskManager

if TYPE_CHECKING:
    from app.pipelines.context import PipelineContext
    from app.pipelines.engine import ProductionEngine
    from app.shorts.settings import ShortsSettings


class ProductionStep(str, Enum):
    SCRIPT = "script"
    SHEET = "sheet"
    IMAGES = "images"
    VOICE = "voice"
    MOVIE = "movie"
    THUMBNAIL = "thumbnail"
    INSTAGRAM = "instagram"
    SHORT_1 = "short1"
    SHORT_2 = "short2"
    EXPORT = "export"


@dataclass(frozen=True)
class StepSpec:
    step: ProductionStep
    task_label: str
    start_log: str
    finish_log: str


PRODUCTION_STEPS: tuple[StepSpec, ...] = (
    StepSpec(ProductionStep.SCRIPT, "Generating Script", "Starting Script...", "Script Finished"),
    StepSpec(
        ProductionStep.SHEET,
        "Generating Production Sheet",
        "Starting Production Sheet...",
        "Production Sheet Finished",
    ),
    StepSpec(ProductionStep.IMAGES, "Generating Images", "Starting Images...", "Images Finished"),
    StepSpec(ProductionStep.VOICE, "Generating Voice", "Starting Voice...", "Voice Finished"),
    StepSpec(ProductionStep.MOVIE, "Rendering Movie", "Starting Movie...", "Movie Finished"),
    # TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
    # StepSpec(
    #     ProductionStep.THUMBNAIL,
    #     "Creating Thumbnail",
    #     "Starting Thumbnail...",
    #     "Thumbnail Finished",
    # ),
    StepSpec(
        ProductionStep.INSTAGRAM,
        "Creating Instagram Image",
        "Starting Instagram Image...",
        "Instagram Finished",
    ),
    StepSpec(ProductionStep.SHORT_1, "Creating Shorts", "Starting Short 1...", "Short 1 Finished"),
    StepSpec(ProductionStep.SHORT_2, "Creating Shorts", "Starting Short 2...", "Short 2 Finished"),
    StepSpec(ProductionStep.EXPORT, "Exporting", "Starting Export...", "Export Finished"),
)


@dataclass(frozen=True)
class GenerationStatus:
    """Live snapshot for the sidebar Status card."""

    task: str
    progress_percent: int
    item: str
    elapsed_seconds: float
    eta_seconds: float | None
    error: str = ""


class GenerationQueue(QObject):
    """Central one-click orchestrator — sequential, no dialogs."""

    status_updated = Signal(object)  # GenerationStatus
    log_line = Signal(str)
    running_changed = Signal(bool)
    finished = Signal(object)  # PipelineResult
    step_changed = Signal(str)

    def __init__(
        self,
        tasks: TaskManager,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tasks = tasks
        self._log = AtlasLog(self)
        self._log.line_written.connect(self.log_line.emit)

        self._running = False
        self._cancel_requested = False
        self._awaiting_idle = False
        self._pending_result: PipelineResult | None = None
        self._active_step: ProductionStep | None = None
        self._step_index = -1
        self._started_at = 0.0
        self._step_fraction = 0.0
        self._last_item = ""
        self._error = ""
        self._logged_image: int | None = None

        self._engine: ProductionEngine | None = None
        self._context: PipelineContext | None = None
        self._channel_name = ""
        self._project_folder = ""
        self._project_dir: Path | None = None

        self._wire_task_signals()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_project(self) -> tuple[str, str] | None:
        if not self._running:
            return None
        return (self._channel_name, self._project_folder)

    def is_job_for(self, channel_name: str, project_folder: str) -> bool:
        return self.active_project == (channel_name, project_folder)

    def start(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        *,
        channel_name: str,
        project_folder: str,
    ) -> bool:
        if self._running or self._tasks.is_busy:
            return False

        self._engine = engine
        self._context = context
        self._channel_name = channel_name
        self._project_folder = project_folder
        self._project_dir = Path(context.project_dir)
        self._log.bind_project(self._project_dir)

        self._running = True
        self._cancel_requested = False
        self._awaiting_idle = False
        self._pending_result = None
        self._active_step = None
        self._step_index = -1
        self._started_at = time.perf_counter()
        self._step_fraction = 0.0
        self._last_item = ""
        self._error = ""
        self._logged_image = None

        self.running_changed.emit(True)
        self._emit_status(task="Starting production…")
        QTimer.singleShot(0, self._advance)
        return True

    def cancel(self) -> None:
        if not self._running:
            return
        self._cancel_requested = True
        self._emit_status(task="Cancelling…", item="Finishing current task")
        if self._tasks.is_busy:
            self._tasks.stop_current()
        elif not self._awaiting_idle:
            QTimer.singleShot(0, self._finish_cancelled)

    def _wire_task_signals(self) -> None:
        t = self._tasks
        t.script_finished.connect(lambda r: self._on_job_finished(ProductionStep.SCRIPT, r))
        t.sheet_finished.connect(lambda r: self._on_job_finished(ProductionStep.SHEET, r))
        t.image_finished.connect(lambda r: self._on_job_finished(ProductionStep.IMAGES, r))
        t.voice_finished.connect(lambda r: self._on_job_finished(ProductionStep.VOICE, r))
        t.movie_finished.connect(lambda r: self._on_job_finished(ProductionStep.MOVIE, r))
        t.thumbnail_finished.connect(
            lambda r: self._on_job_finished(ProductionStep.THUMBNAIL, r)
        )
        t.instagram_finished.connect(
            lambda r: self._on_job_finished(ProductionStep.INSTAGRAM, r)
        )
        t.shorts_finished.connect(self._on_shorts_finished)
        t.export_finished.connect(lambda r: self._on_job_finished(ProductionStep.EXPORT, r))

        t.script_running_changed.connect(
            lambda running: self._on_job_idle(ProductionStep.SCRIPT, running)
        )
        t.sheet_running_changed.connect(
            lambda running: self._on_job_idle(ProductionStep.SHEET, running)
        )
        t.image_running_changed.connect(
            lambda running: self._on_job_idle(ProductionStep.IMAGES, running)
        )
        t.voice_running_changed.connect(
            lambda running: self._on_job_idle(ProductionStep.VOICE, running)
        )
        t.movie_running_changed.connect(
            lambda running: self._on_job_idle(ProductionStep.MOVIE, running)
        )
        t.thumbnail_running_changed.connect(
            lambda running: self._on_job_idle(ProductionStep.THUMBNAIL, running)
        )
        t.instagram_running_changed.connect(
            lambda running: self._on_job_idle(ProductionStep.INSTAGRAM, running)
        )
        t.shorts_running_changed.connect(self._on_shorts_idle)
        t.export_running_changed.connect(
            lambda running: self._on_job_idle(ProductionStep.EXPORT, running)
        )

        t.image_progress.connect(self._on_image_progress)
        t.voice_progress.connect(self._on_voice_progress)
        t.movie_progress.connect(self._on_movie_progress)
        t.thumbnail_progress.connect(self._on_thumbnail_progress)
        t.shorts_progress.connect(self._on_shorts_progress)
        t.script_progress.connect(lambda msg: self._on_simple_progress(msg))
        t.sheet_progress.connect(lambda msg: self._on_simple_progress(msg))
        t.instagram_progress.connect(lambda msg: self._on_simple_progress(msg))
        t.export_progress.connect(lambda msg: self._on_simple_progress(msg))

    def _advance(self) -> None:
        if not self._running:
            return

        if self._cancel_requested:
            self._finish_cancelled()
            return

        next_index = self._step_index + 1
        if next_index >= len(PRODUCTION_STEPS):
            self._write("Production Completed")
            result = PipelineResult.success("Production Completed")
            self._complete(result)
            return

        spec = PRODUCTION_STEPS[next_index]
        self._step_index = next_index
        self._active_step = spec.step
        self._step_fraction = 0.0
        self._last_item = ""
        self._pending_result = None
        self._awaiting_idle = False

        self.step_changed.emit(spec.task_label)
        self._write(spec.start_log)
        self._emit_status(task=spec.task_label)

        if not self._start_step(spec.step):
            self._fail(f"Could not start step: {spec.task_label}")

    def _start_step(self, step: ProductionStep) -> bool:
        engine = self._engine
        context = self._context
        if engine is None or context is None:
            return False

        kwargs = {
            "channel_name": self._channel_name,
            "project_folder": self._project_folder,
        }

        if step is ProductionStep.SCRIPT:
            return self._tasks.start_script(engine, context, **kwargs)
        if step is ProductionStep.SHEET:
            return self._tasks.start_sheet(engine, context, **kwargs)
        if step is ProductionStep.IMAGES:
            return self._tasks.start_images(engine, context, **kwargs)
        if step is ProductionStep.VOICE:
            return self._tasks.start_voice(engine, context, **kwargs)
        if step is ProductionStep.MOVIE:
            return self._tasks.start_movie(engine, context, **kwargs)
        if step is ProductionStep.THUMBNAIL:
            return self._tasks.start_thumbnail(engine, context, **kwargs)
        if step is ProductionStep.INSTAGRAM:
            from app.tasks.instagram_export import create_instagram_image

            project_dir = self._project_dir or Path(context.project_dir)

            def work() -> PipelineResult:
                return create_instagram_image(project_dir)

            return self._tasks.start_instagram(
                work, engine=engine, **kwargs
            )
        if step is ProductionStep.SHORT_1:
            from app.shorts.settings import ShortsSettings

            return self._tasks.start_shorts(
                engine,
                context,
                settings=ShortsSettings(
                    max_shorts=1,
                    max_duration_sec=30.0,
                    min_duration_sec=20.0,
                    independent_creative=True,
                ),
                **kwargs,
            )
        if step is ProductionStep.SHORT_2:
            from app.shorts.settings import ShortsSettings

            return self._tasks.start_shorts(
                engine,
                context,
                settings=ShortsSettings(
                    max_shorts=2,
                    max_duration_sec=30.0,
                    min_duration_sec=20.0,
                    independent_creative=True,
                ),
                **kwargs,
            )
        if step is ProductionStep.EXPORT:
            from app.projects.assets.registry import AssetRegistry
            from app.tasks.instagram_export import verify_youtube_export

            project_dir = self._project_dir or Path(context.project_dir)

            def work() -> PipelineResult:
                result = verify_youtube_export(project_dir)
                try:
                    AssetRegistry(project_dir).record_pipeline_result("export", result)
                except Exception:  # noqa: BLE001
                    pass
                return result

            return self._tasks.start_export(work, engine=engine, **kwargs)
        return False

    def _on_job_finished(self, step: ProductionStep, result: PipelineResult) -> None:
        if not self._running or self._active_step is not step:
            return
        self._pending_result = result
        self._awaiting_idle = True
        if not self._tasks.is_busy:
            self._consume_pending()

    def _on_shorts_finished(self, result: PipelineResult) -> None:
        if not self._running or self._active_step not in {
            ProductionStep.SHORT_1,
            ProductionStep.SHORT_2,
        }:
            return
        self._pending_result = result
        self._awaiting_idle = True
        if not self._tasks.is_busy:
            self._consume_pending()

    def _on_job_idle(self, step: ProductionStep, running: bool) -> None:
        if running or not self._running:
            return
        if self._active_step is not step:
            return
        if self._awaiting_idle and self._pending_result is not None:
            self._consume_pending()

    def _on_shorts_idle(self, running: bool) -> None:
        if running or not self._running:
            return
        if self._active_step not in {ProductionStep.SHORT_1, ProductionStep.SHORT_2}:
            return
        if self._awaiting_idle and self._pending_result is not None:
            self._consume_pending()

    def _consume_pending(self) -> None:
        result = self._pending_result
        self._pending_result = None
        self._awaiting_idle = False
        if result is None or not self._running:
            return

        if self._cancel_requested or result.outcome == PipelineOutcome.CANCELLED:
            self._finish_cancelled()
            return

        if result.outcome == PipelineOutcome.FAILED:
            message = result.message or (result.errors[0] if result.errors else "Fatal error")
            self._fail(message)
            return

        spec = PRODUCTION_STEPS[self._step_index]
        self._write(spec.finish_log)
        self._step_fraction = 1.0
        self._emit_status(task=spec.task_label)
        QTimer.singleShot(0, self._advance)

    def _finish_cancelled(self) -> None:
        self._write("Generation Cancelled")
        self._error = "Generation Cancelled"
        self._emit_status(task="Generation Cancelled", error=self._error)
        self._complete(PipelineResult.cancelled("Generation Cancelled"))

    def _fail(self, message: str) -> None:
        self._error = message
        self._write(f"Error: {message}")
        self._emit_status(task="Failed", item=message, error=message)
        self._complete(PipelineResult.failed(message, errors=[message]))

    def _complete(self, result: PipelineResult) -> None:
        if result.ok and self._channel_name:
            self._record_brain_memory(result)
        self._running = False
        self._active_step = None
        self._cancel_requested = False
        self._awaiting_idle = False
        self._pending_result = None
        self.running_changed.emit(False)
        self.finished.emit(result)

    def _record_brain_memory(self, result: PipelineResult) -> None:
        """Learn from own production — never fails the queue."""
        try:
            from app.brain.learning import record_production_memory
            from app.brain.service import ChannelBrainService

            engine = self._engine
            config = getattr(engine, "_config", None) if engine is not None else None
            data_root = getattr(config, "data_root", None)
            if data_root is None:
                return
            topic = ""
            if self._context is not None:
                topic = str(getattr(self._context.project, "idea", "") or "")
            record_production_memory(
                ChannelBrainService(data_root),
                channel=self._channel_name,
                project=self._project_folder,
                topic=topic,
                quality="success" if result.outcome == PipelineOutcome.SUCCESS else "warning",
                notes=(result.message or "")[:240],
                settings={"artifacts": list(result.artifacts or [])[:20]},
            )
        except Exception:  # noqa: BLE001
            return

    def _write(self, message: str) -> None:
        self._log.write(message)

    def _overall_percent(self) -> int:
        total = len(PRODUCTION_STEPS)
        if total <= 0:
            return 0
        index = max(0, self._step_index)
        frac = max(0.0, min(1.0, self._step_fraction))
        if self._step_index < 0:
            return 0
        value = ((index + frac) / total) * 100.0
        return int(max(0, min(100, round(value))))

    def _eta_seconds(self, elapsed: float, percent: int) -> float | None:
        if percent <= 0 or elapsed <= 0:
            return None
        remaining = 100 - percent
        if remaining <= 0:
            return 0.0
        return (elapsed / percent) * remaining

    def _emit_status(
        self,
        *,
        task: str | None = None,
        item: str | None = None,
        error: str | None = None,
    ) -> None:
        elapsed = time.perf_counter() - self._started_at if self._started_at else 0.0
        percent = self._overall_percent()
        status = GenerationStatus(
            task=task
            if task is not None
            else (PRODUCTION_STEPS[self._step_index].task_label if self._step_index >= 0 else "Ready"),
            progress_percent=percent,
            item=self._last_item if item is None else item,
            elapsed_seconds=elapsed,
            eta_seconds=self._eta_seconds(elapsed, percent),
            error=self._error if error is None else error,
        )
        self.status_updated.emit(status)

    def _on_simple_progress(self, message: str) -> None:
        if not self._running:
            return
        self._last_item = message
        self._emit_status()

    def _on_image_progress(self, progress) -> None:
        if not self._running or self._active_step is not ProductionStep.IMAGES:
            return
        total = max(1, int(progress.total or 0))
        current = int(progress.current or 0)
        self._step_fraction = min(1.0, current / total) if total else 0.0
        self._last_item = f"Image {current} / {total}"
        if current > 0 and current != self._logged_image:
            self._logged_image = current
            self._write(f"Generating Image {current}/{total}")
        self._emit_status(task="Generating Images")

    def _on_voice_progress(self, progress) -> None:
        if not self._running or self._active_step is not ProductionStep.VOICE:
            return
        total = int(progress.total or 0)
        current = int(progress.current or 0)
        if total > 0:
            self._step_fraction = min(1.0, current / total)
            self._last_item = f"Voice {current} / {total}"
        else:
            self._last_item = progress.message or "Generating Voice"
        self._emit_status(task="Generating Voice")

    def _on_movie_progress(self, progress) -> None:
        if not self._running or self._active_step is not ProductionStep.MOVIE:
            return
        total = max(1, int(progress.total or 0))
        current = int(progress.current or 0)
        self._step_fraction = min(1.0, current / total) if total else 0.0
        label = progress.scene_label or progress.message or ""
        self._last_item = f"Movie Scene {current} / {total}"
        if label and label not in self._last_item:
            self._last_item = f"{self._last_item} — {label}"
        self._emit_status(task="Rendering Movie")

    def _on_thumbnail_progress(self, progress) -> None:
        if not self._running or self._active_step is not ProductionStep.THUMBNAIL:
            return
        self._last_item = progress.message or progress.stage or "Creating Thumbnail"
        self._step_fraction = 0.5
        self._emit_status(task="Creating Thumbnail")

    def _on_shorts_progress(self, progress) -> None:
        if not self._running or self._active_step not in {
            ProductionStep.SHORT_1,
            ProductionStep.SHORT_2,
        }:
            return
        total = int(progress.total or 0)
        current = int(progress.current or 0)
        if total > 0 and current > 0:
            self._step_fraction = min(1.0, current / total)
            self._last_item = f"Short {current} / {total}"
        else:
            self._last_item = progress.message or "Creating Shorts"
        task = (
            "Creating Shorts"
            if self._active_step is ProductionStep.SHORT_2
            else "Creating Shorts"
        )
        self._emit_status(task=task)
