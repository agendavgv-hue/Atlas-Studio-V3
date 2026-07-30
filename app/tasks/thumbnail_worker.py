"""Background worker for Thumbnail Pipeline execution."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal

from app.pipelines.context import PipelineContext
from app.pipelines.engine import ProductionEngine
from app.pipelines.results import PipelineResult
from app.thumbnail.progress import ThumbnailQueueProgress


class ThumbnailGenerationWorker(QObject):
    """Runs generate_thumbnail on a worker thread. Owned by TaskManager."""

    progress = Signal(object)  # ThumbnailQueueProgress
    finished = Signal(object)  # PipelineResult
    failed = Signal(str)

    def __init__(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._context = context
        self._started = 0.0

    def run(self) -> None:
        self._started = time.perf_counter()

        def on_progress(message: str, stage: str = "") -> None:
            elapsed = time.perf_counter() - self._started
            self.progress.emit(
                ThumbnailQueueProgress(
                    message=message,
                    stage=stage,
                    elapsed_seconds=elapsed,
                )
            )

        try:
            result = self._engine.generate_thumbnail(
                self._context,
                on_queue_progress=on_progress,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)
