"""Application-level task manager — pipelines outlive page navigation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QThread, Signal

from app.pipelines.results import PipelineOutcome, PipelineResult

if TYPE_CHECKING:
    from app.pipelines.context import PipelineContext
    from app.pipelines.engine import ProductionEngine
    from app.pipelines.image_progress import ImageQueueProgress
    from app.pipelines.voice_progress import VoiceQueueProgress
    from app.render.progress import MovieQueueProgress
    from app.shorts.settings import ShortsSettings
    from app.tasks.pipeline_worker import EngineCallable
    from app.tasks.shorts_worker import ShortsQueueProgress
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

    script_progress = Signal(str)
    script_finished = Signal(object)
    script_running_changed = Signal(bool)
    sheet_progress = Signal(str)
    sheet_finished = Signal(object)
    sheet_running_changed = Signal(bool)
    shorts_progress = Signal(object)
    shorts_finished = Signal(object)
    shorts_running_changed = Signal(bool)
    instagram_progress = Signal(str)
    instagram_finished = Signal(object)
    instagram_running_changed = Signal(bool)
    export_progress = Signal(str)
    export_finished = Signal(object)
    export_running_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine: ProductionEngine | None = None
        self._thread: QThread | None = None
        self._worker = None
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
    def is_script_running(self) -> bool:
        return self.is_busy and self._job_kind == "script"

    @property
    def is_sheet_running(self) -> bool:
        return self.is_busy and self._job_kind == "sheet"

    @property
    def is_shorts_running(self) -> bool:
        return self.is_busy and self._job_kind == "shorts"

    @property
    def is_instagram_running(self) -> bool:
        return self.is_busy and self._job_kind == "instagram"

    @property
    def is_export_running(self) -> bool:
        return self.is_busy and self._job_kind == "export"

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

    def start_script(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        *,
        channel_name: str,
        project_folder: str,
    ) -> bool:
        if self.is_busy:
            return False

        def work() -> PipelineResult:
            return engine.regenerate_script(context)

        return self._start_callable_job(
            "script",
            engine,
            work,
            channel_name,
            project_folder,
            status="Generating Script…",
            start_message="Generating Script…",
            running_signal=self.script_running_changed,
            progress_signal=self.script_progress,
            finished_slot=self._on_script_finished,
            failed_slot=self._on_script_failed,
        )

    def start_sheet(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        *,
        channel_name: str,
        project_folder: str,
    ) -> bool:
        if self.is_busy:
            return False

        def work() -> PipelineResult:
            return engine.regenerate_production_sheet(context)

        return self._start_callable_job(
            "sheet",
            engine,
            work,
            channel_name,
            project_folder,
            status="Generating Production Sheet…",
            start_message="Generating Production Sheet…",
            running_signal=self.sheet_running_changed,
            progress_signal=self.sheet_progress,
            finished_slot=self._on_sheet_finished,
            failed_slot=self._on_sheet_failed,
        )

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
        from app.tasks.image_worker import ImageGenerationWorker

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
        from app.tasks.voice_worker import VoiceGenerationWorker

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
        from app.tasks.movie_worker import MovieGenerationWorker

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
        from app.tasks.thumbnail_worker import ThumbnailGenerationWorker

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

    def start_shorts(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        *,
        channel_name: str,
        project_folder: str,
        settings: ShortsSettings | None = None,
    ) -> bool:
        if self.is_busy:
            return False
        from app.tasks.shorts_worker import ShortsGenerationWorker

        return self._start_job(
            "shorts",
            engine,
            ShortsGenerationWorker(engine, context, settings=settings),
            channel_name,
            project_folder,
            status="Creating Shorts…",
            running_signal=self.shorts_running_changed,
            progress_slot=self._on_shorts_progress,
            finished_slot=self._on_shorts_finished,
            failed_slot=self._on_shorts_failed,
        )

    def start_instagram(
        self,
        work: EngineCallable,
        *,
        channel_name: str,
        project_folder: str,
        engine: ProductionEngine | None = None,
    ) -> bool:
        if self.is_busy:
            return False
        return self._start_callable_job(
            "instagram",
            engine if engine is not None else self._engine,
            work,
            channel_name,
            project_folder,
            status="Creating Instagram Image…",
            start_message="Creating Instagram Image…",
            running_signal=self.instagram_running_changed,
            progress_signal=self.instagram_progress,
            finished_slot=self._on_instagram_finished,
            failed_slot=self._on_instagram_failed,
        )

    def start_export(
        self,
        work: EngineCallable,
        *,
        channel_name: str,
        project_folder: str,
        engine: ProductionEngine | None = None,
    ) -> bool:
        if self.is_busy:
            return False
        return self._start_callable_job(
            "export",
            engine if engine is not None else self._engine,
            work,
            channel_name,
            project_folder,
            status="Exporting…",
            start_message="Verifying export…",
            running_signal=self.export_running_changed,
            progress_signal=self.export_progress,
            finished_slot=self._on_export_finished,
            failed_slot=self._on_export_failed,
        )

    def _start_callable_job(
        self,
        kind: str,
        engine: ProductionEngine | None,
        work: EngineCallable,
        channel_name: str,
        project_folder: str,
        *,
        status: str,
        start_message: str,
        running_signal,
        progress_signal,
        finished_slot,
        failed_slot,
    ) -> bool:
        from app.tasks.pipeline_worker import PipelineCallableWorker

        worker = PipelineCallableWorker(work, start_message=start_message)
        thread = QThread()
        self._engine = engine
        self._job_kind = kind
        self._job = (channel_name, project_folder)
        self._set_status(status)
        running_signal.emit(True)

        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(progress_signal.emit)
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
        self.stop_current(status="Stopping after current image…")

    def stop_voice(self) -> None:
        self.stop_current(status="Stopping voice…")

    def stop_movie(self) -> None:
        self.stop_current(status="Stopping after current scene…")

    def stop_thumbnail(self) -> None:
        self.stop_current(status="Stopping thumbnail…")

    def stop_shorts(self) -> None:
        self.stop_current(status="Stopping shorts…")

    def stop_current(self, *, status: str | None = None) -> None:
        if self._engine is not None:
            self._engine.request_cancel()
        if self.is_busy:
            self._set_status(status or "Stopping…")

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

    def _on_script_finished(self, result: PipelineResult) -> None:
        self._set_status(self._status_for_result(result))
        self.script_finished.emit(result)

    def _on_script_failed(self, message: str) -> None:
        self._set_status("Failed")
        self.script_finished.emit(PipelineResult.failed(message, errors=[message]))

    def _on_sheet_finished(self, result: PipelineResult) -> None:
        self._set_status(self._status_for_result(result))
        self.sheet_finished.emit(result)

    def _on_sheet_failed(self, message: str) -> None:
        self._set_status("Failed")
        self.sheet_finished.emit(PipelineResult.failed(message, errors=[message]))

    def _on_shorts_progress(self, progress: ShortsQueueProgress) -> None:
        self._set_status(f"Creating Shorts — {progress.message}")
        self.shorts_progress.emit(progress)

    def _on_shorts_finished(self, result: PipelineResult) -> None:
        self._set_status(self._status_for_result(result))
        self.shorts_finished.emit(result)

    def _on_shorts_failed(self, message: str) -> None:
        self._set_status("Failed")
        self.shorts_finished.emit(PipelineResult.failed(message, errors=[message]))

    def _on_instagram_finished(self, result: PipelineResult) -> None:
        self._set_status(self._status_for_result(result))
        self.instagram_finished.emit(result)

    def _on_instagram_failed(self, message: str) -> None:
        self._set_status("Failed")
        self.instagram_finished.emit(PipelineResult.failed(message, errors=[message]))

    def _on_export_finished(self, result: PipelineResult) -> None:
        self._set_status(self._status_for_result(result))
        self.export_finished.emit(result)

    def _on_export_failed(self, message: str) -> None:
        self._set_status("Failed")
        self.export_finished.emit(PipelineResult.failed(message, errors=[message]))

    def _on_thread_finished(self) -> None:
        kind = self._job_kind
        self._thread = None
        self._worker = None
        self._job = None
        self._job_kind = None
        running_map = {
            "images": self.image_running_changed,
            "voice": self.voice_running_changed,
            "movie": self.movie_running_changed,
            "thumbnail": self.thumbnail_running_changed,
            "script": self.script_running_changed,
            "sheet": self.sheet_running_changed,
            "shorts": self.shorts_running_changed,
            "instagram": self.instagram_running_changed,
            "export": self.export_running_changed,
        }
        signal = running_map.get(kind or "")
        if signal is not None:
            signal.emit(False)
        if self._status.startswith("Stopping") or self._status.startswith("Generating") or self._status.startswith(
            "Creating"
        ) or self._status.startswith("Exporting"):
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
