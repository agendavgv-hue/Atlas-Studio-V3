"""Background worker for Movie Pipeline execution."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal

from app.pipelines.context import PipelineContext
from app.pipelines.engine import ProductionEngine
from app.pipelines.results import PipelineResult
from app.render.progress import MovieQueueProgress


class MovieGenerationWorker(QObject):
    """Runs generate_movie on a worker thread. Owned by TaskManager."""

    progress = Signal(object)  # MovieQueueProgress
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

        def on_progress(
            current: int,
            total: int,
            message: str,
            stage: str = "scene",
            scene_label: str = "",
        ) -> None:
            elapsed = time.perf_counter() - self._started
            eta = None
            if current > 0 and total > 0:
                per = elapsed / current
                eta = max(0.0, per * (total - current))
            self.progress.emit(
                MovieQueueProgress(
                    current=current,
                    total=total,
                    message=message,
                    stage=stage,
                    scene_label=scene_label,
                    elapsed_seconds=elapsed,
                    eta_seconds=eta,
                )
            )

        try:
            result = self._engine.generate_movie(
                self._context,
                on_queue_progress=on_progress,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)
