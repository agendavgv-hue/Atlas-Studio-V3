"""Background worker for Shorts Pipeline execution."""

from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from app.pipelines.context import PipelineContext
from app.pipelines.engine import ProductionEngine
from app.pipelines.results import PipelineResult
from app.shorts.settings import ShortsSettings


@dataclass(frozen=True)
class ShortsQueueProgress:
    message: str
    stage: str = ""
    current: int = 0
    total: int = 0
    elapsed_seconds: float = 0.0


class ShortsGenerationWorker(QObject):
    """Runs generate_shorts on a worker thread. Owned by TaskManager."""

    progress = Signal(object)  # ShortsQueueProgress
    finished = Signal(object)  # PipelineResult
    failed = Signal(str)

    def __init__(
        self,
        engine: ProductionEngine,
        context: PipelineContext,
        *,
        settings: ShortsSettings | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._context = context
        self._settings = settings
        self._started = 0.0

    def run(self) -> None:
        self._started = time.perf_counter()

        def on_progress(message: str, stage: str) -> None:
            current = 0
            total = 0
            # "Generating short 1 / 2"
            lower = message.lower()
            if "short" in lower and "/" in message:
                try:
                    left, right = message.rsplit("/", 1)
                    total = int("".join(ch for ch in right if ch.isdigit()) or "0")
                    current = int("".join(ch for ch in left if ch.isdigit()) or "0")
                except ValueError:
                    current, total = 0, 0
            elapsed = time.perf_counter() - self._started
            self.progress.emit(
                ShortsQueueProgress(
                    message=message,
                    stage=stage,
                    current=current,
                    total=total,
                    elapsed_seconds=elapsed,
                )
            )

        try:
            result = self._engine.generate_shorts(
                self._context,
                on_queue_progress=on_progress,
                settings=self._settings,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)
