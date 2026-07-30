"""Application-level task manager — pipelines outlive page navigation."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from app.pipelines.context import PipelineContext
from app.pipelines.engine import ProductionEngine
from app.pipelines.image_progress import ImageQueueProgress
from app.pipelines.results import PipelineOutcome, PipelineResult
from app.pipelines.voice_progress import VoiceQueueProgress
from app.render.progress import MovieQueueProgress
from app.tasks.image_worker import ImageGenerationWorker
from app.tasks.movie_worker import MovieGenerationWorker
from app.tasks.thumbnail_worker import ThumbnailGenerationWorker
from app.tasks.voice_worker import VoiceGenerationWorker
from app.thumbnail.progress import ThumbnailQueueProgress


class TaskManager(QObject):
    """Central owner of long-running production work."""

    status_changed = Signal(str)
    image_progress = Signal(object)
    image_finished = Signal(object)
    image_running_changed = Signal(bool)
    voice_progress = Signal(object)
    voice_finished = Signal(object)
    voice_running_changed = Signal(bool)
    movie_progress = Signal(object)
    movie_finished = Signal(object)
    movie_running_changed = Signal(bool)
    thumbnail_progress = Signal(object)
    thumbnail_finished = Signal(object)
    thumbnail_running_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine: ProductionEngine | None = None
        self._thread: QThread | None = None
        self._worker: (
            ImageGenerationWorker
            | VoiceGenerationWorker
            | MovieGenerationWorker
            | ThumbnailGenerationWorker
            | None
        ) = None
        self._job_kind: str | None = None
        self._job: tuple[str, str] | None = None
        self._status = "Ready"
        self.status_changed.emit(self._status)

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_busy(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @property
    def is_images_running(self) -> bool:
        return self.is_busy and self._job_kind == "images"

    @property
    def is_voice_running(self) -> bool:
        return self.is_busy and self._job_kind == "voice"

    @property
    def is_movie_running(self) -> bool:
        return self.is_busy and self._job_kind == "movie"

    @property
    def is_thumbnail_running(self) -> bool:
        return self.is_busy and self._job_kind == "thumbnail"

    @property
    def active_image_job(self) -> tuple[str, str] | None:
        return self._job if self._job_kind == "images" else None

    @property
    def active_voice_job(self) -> tuple[str, str] | None:
        return self._job if self._job_kind == "voice" else None

    @property
    def active_movie_job(self) -> tuple[str, str] | None:
        return self._job if self._job_kind == "movie" else None

    @property
    def active_thumbnail_job(self) -> tuple[str, str] | None:
        return self._job if self._job_kind == "thumbnail" else None

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
        if self.is_busy:
            return False
        return self._start_job(
            "images",
            engine,
            ImageGenerationWorker(engine, context),
            channel_name,
            project_folder,
            status="Generating Images…",
            running_signal=self.image_running_changed,
            progress_slot=self._on_image_progress,
            finished_slot=self._on_image_finished,
            failed_slot=self._on_image_failed,
        )

    def start_voice(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        *,
        channel_name: str,
        project_folder: str,
    ) -> bool:
        if self.is_busy:
            return False
        return self._start_job(
            "voice",
            engine,
            VoiceGenerationWorker(engine, context),
            channel_name,
            project_folder,
            status="Generating Voice…",
            running_signal=self.voice_running_changed,
            progress_slot=self._on_voice_progress,
            finished_slot=self._on_voice_finished,
            failed_slot=self._on_voice_failed,
        )

    def start_movie(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        *,
        channel_name: str,
        project_folder: str,
    ) -> bool:
        if self.is_busy:
            return False
        return self._start_job(
            "movie",
            engine,
            MovieGenerationWorker(engine, context),
            channel_name,
            project_folder,
            status="Generating Movie…",
            running_signal=self.movie_running_changed,
            progress_slot=self._on_movie_progress,
            finished_slot=self._on_movie_finished,
            failed_slot=self._on_movie_failed,
        )

    def start_thumbnail(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        *,
        channel_name: str,
        project_folder: str,
    ) -> bool:
        if self.is_busy:
            return False
        return self._start_job(
            "thumbnail",
            engine,
            ThumbnailGenerationWorker(engine, context),
            channel_name,
            project_folder,
            status="Generating Thumbnail…",
            running_signal=self.thumbnail_running_changed,
            progress_slot=self._on_thumbnail_progress,
            finished_slot=self._on_thumbnail_finished,
            failed_slot=self._on_thumbnail_failed,
        )

    def _start_job(
        self,
        kind: str,
        engine: ProductionEngine,
        worker,
        channel_name: str,
        project_folder: str,
        *,
        status: str,
        running_signal,
        progress_slot,
        finished_slot,
        failed_slot,
    ) -> bool:
        self._engine = engine
        self._job_kind = kind
        self._job = (channel_name, project_folder)
        self._set_status(status)
        running_signal.emit(True)

        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(progress_slot)
        worker.finished.connect(finished_slot)
        worker.failed.connect(failed_slot)
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
        if self._engine is not None:
            self._engine.request_cancel()
        if self.is_images_running:
            self._set_status("Stopping after current image…")

    def stop_voice(self) -> None:
        if self._engine is not None:
            self._engine.request_cancel()
        if self.is_voice_running:
            self._set_status("Stopping voice…")

    def stop_movie(self) -> None:
        if self._engine is not None:
            self._engine.request_cancel()
        if self.is_movie_running:
            self._set_status("Stopping after current scene…")

    def stop_thumbnail(self) -> None:
        if self._engine is not None:
            self._engine.request_cancel()
        if self.is_thumbnail_running:
            self._set_status("Stopping thumbnail…")

    def is_job_for(self, channel_name: str, project_folder: str) -> bool:
        return self._job == (channel_name, project_folder)

    def _on_image_progress(self, progress: ImageQueueProgress) -> None:
        self._set_status(f"Generating Images ({progress.current} / {progress.total})")
        self.image_progress.emit(progress)

    def _on_image_finished(self, result: PipelineResult) -> None:
        self._set_status(self._status_for_result(result))
        self.image_finished.emit(result)

    def _on_image_failed(self, message: str) -> None:
        self._set_status("Failed")
        self.image_finished.emit(PipelineResult.failed(message, errors=[message]))

    def _on_voice_progress(self, progress: VoiceQueueProgress) -> None:
        self._set_status(f"Generating Voice — {progress.message}")
        self.voice_progress.emit(progress)

    def _on_voice_finished(self, result: PipelineResult) -> None:
        self._set_status(self._status_for_result(result))
        self.voice_finished.emit(result)

    def _on_voice_failed(self, message: str) -> None:
        self._set_status("Failed")
        self.voice_finished.emit(PipelineResult.failed(message, errors=[message]))

    def _on_movie_progress(self, progress: MovieQueueProgress) -> None:
        self._set_status(f"Generating Movie ({progress.current} / {progress.total})")
        self.movie_progress.emit(progress)

    def _on_movie_finished(self, result: PipelineResult) -> None:
        self._set_status(self._status_for_result(result))
        self.movie_finished.emit(result)

    def _on_movie_failed(self, message: str) -> None:
        self._set_status("Failed")
        self.movie_finished.emit(PipelineResult.failed(message, errors=[message]))

    def _on_thumbnail_progress(self, progress: ThumbnailQueueProgress) -> None:
        self._set_status(f"Generating Thumbnail — {progress.message}")
        self.thumbnail_progress.emit(progress)

    def _on_thumbnail_finished(self, result: PipelineResult) -> None:
        self._set_status(self._status_for_result(result))
        self.thumbnail_finished.emit(result)

    def _on_thumbnail_failed(self, message: str) -> None:
        self._set_status("Failed")
        self.thumbnail_finished.emit(PipelineResult.failed(message, errors=[message]))

    def _on_thread_finished(self) -> None:
        kind = self._job_kind
        self._thread = None
        self._worker = None
        self._job = None
        self._job_kind = None
        if kind == "images":
            self.image_running_changed.emit(False)
        elif kind == "voice":
            self.voice_running_changed.emit(False)
        elif kind == "movie":
            self.movie_running_changed.emit(False)
        elif kind == "thumbnail":
            self.thumbnail_running_changed.emit(False)
        if self._status.startswith("Stopping") or self._status.startswith("Generating"):
            self._set_status("Ready")

    @staticmethod
    def _status_for_result(result: PipelineResult) -> str:
        if result.outcome == PipelineOutcome.CANCELLED:
            return "Cancelled"
        if result.outcome == PipelineOutcome.FAILED:
            return "Failed"
        return "Completed"

    def _set_status(self, text: str) -> None:
        self._status = text
        self.status_changed.emit(text)
