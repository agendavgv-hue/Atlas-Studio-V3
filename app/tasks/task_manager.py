"""Application-level task manager — pipelines outlive page navigation."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from app.pipelines.context import PipelineContext
from app.pipelines.engine import ProductionEngine
from app.pipelines.image_progress import ImageQueueProgress
from app.pipelines.results import PipelineOutcome, PipelineResult
from app.tasks.image_worker import ImageGenerationWorker


class TaskManager(QObject):
    """Central owner of long-running production work."""

    status_changed = Signal(str)
    image_progress = Signal(object)  # ImageQueueProgress
    image_finished = Signal(object)  # PipelineResult
    image_running_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine: ProductionEngine | None = None
        self._thread: QThread | None = None
        self._worker: ImageGenerationWorker | None = None
        self._image_job: tuple[str, str] | None = None  # channel, folder
        self._status = "Ready"
        self.status_changed.emit(self._status)

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_images_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @property
    def active_image_job(self) -> tuple[str, str] | None:
        return self._image_job

    def bind_engine(self, engine: ProductionEngine) -> None:
        self._engine = engine

    def start_images(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        *,
        channel_name: str,
        project_folder: str,
    ) -> bool:
        """Start image generation. Returns False if a job is already running."""
        if self.is_images_running:
            return False

        self._engine = engine
        self._image_job = (channel_name, project_folder)
        self._set_status("Generating Images…")
        self.image_running_changed.emit(True)

        thread = QThread()
        worker = ImageGenerationWorker(engine, context)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_image_progress)
        worker.finished.connect(self._on_image_finished)
        worker.failed.connect(self._on_image_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)

        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    def stop_images(self) -> None:
        """Request cooperative cancel after the current image finishes."""
        if self._engine is not None:
            self._engine.request_cancel()
        if self.is_images_running:
            self._set_status("Stopping after current image…")

    def is_job_for(self, channel_name: str, project_folder: str) -> bool:
        return self._image_job == (channel_name, project_folder)

    def _on_image_progress(self, progress: ImageQueueProgress) -> None:
        self._set_status(f"Generating Images ({progress.current} / {progress.total})")
        self.image_progress.emit(progress)

    def _on_image_finished(self, result: PipelineResult) -> None:
        if result.outcome == PipelineOutcome.CANCELLED:
            self._set_status("Cancelled")
        elif result.outcome == PipelineOutcome.FAILED:
            self._set_status("Failed")
        elif result.outcome == PipelineOutcome.WARNING:
            self._set_status("Completed")
        else:
            self._set_status("Completed")
        self.image_finished.emit(result)

    def _on_image_failed(self, message: str) -> None:
        self._set_status("Failed")
        failed = PipelineResult.failed(message, errors=[message])
        self.image_finished.emit(failed)

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._image_job = None
        self.image_running_changed.emit(False)
        # Keep Cancelled/Completed/Failed until next job; Ready only if still "Stopping…"
        if self._status.startswith("Stopping") or self._status.startswith("Generating"):
            self._set_status("Ready")

    def _set_status(self, text: str) -> None:
        self._status = text
        self.status_changed.emit(text)
