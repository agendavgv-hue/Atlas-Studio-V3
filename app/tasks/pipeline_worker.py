"""Generic background worker for ProductionEngine callables."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from app.pipelines.results import PipelineResult

EngineCallable = Callable[[], PipelineResult]


class PipelineCallableWorker(QObject):
    """Runs a zero-arg engine callable on a worker thread."""

    progress = Signal(str)
    finished = Signal(object)  # PipelineResult
    failed = Signal(str)

    def __init__(
        self,
        work: EngineCallable,
        *,
        start_message: str = "Working…",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._work = work
        self._start_message = start_message

    def run(self) -> None:
        self.progress.emit(self._start_message)
        try:
            result = self._work()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)
