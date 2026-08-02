"""Background section loader for Channel Studio (never blocks UI)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from app.channels.studio.service import ChannelStudioService


@dataclass
class SectionLoadResult:
    folder_name: str
    section: str
    payload: Any
    generation: int


class SectionLoadWorker(QObject):
    finished = Signal(object)  # SectionLoadResult
    failed = Signal(str, str, int)  # section, message, generation

    def __init__(
        self,
        data_root: Path,
        folder_name: str,
        section: str,
        generation: int,
    ) -> None:
        super().__init__()
        self._data_root = Path(data_root)
        self._folder = folder_name
        self._section = section
        self._generation = generation

    def run(self) -> None:
        try:
            service = ChannelStudioService(self._data_root)
            payload = service.load_section(self._folder, self._section)
            self.finished.emit(
                SectionLoadResult(
                    folder_name=self._folder,
                    section=self._section,
                    payload=payload,
                    generation=self._generation,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(self._section, str(exc), self._generation)


class SectionLoadController(QObject):
    """Owns one background load at a time; ignores stale results."""

    section_ready = Signal(object)  # SectionLoadResult
    section_failed = Signal(str, str)  # section, message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: SectionLoadWorker | None = None
        self._generation = 0
        self._pending: str | None = None

    @property
    def pending_section(self) -> str | None:
        return self._pending

    def cancel(self) -> None:
        self._generation += 1
        self._pending = None
        self._detach_thread()

    def load(self, data_root: Path, folder_name: str, section: str) -> None:
        self.cancel()
        generation = self._generation
        self._pending = section
        thread = QThread()
        worker = SectionLoadWorker(data_root, folder_name, section, generation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_finished(self, result: object) -> None:
        if not isinstance(result, SectionLoadResult):
            return
        if result.generation != self._generation:
            return
        self._pending = None
        self.section_ready.emit(result)

    def _on_failed(self, section: str, message: str, generation: int) -> None:
        if generation != self._generation:
            return
        self._pending = None
        self.section_failed.emit(section, message)

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None

    def _detach_thread(self) -> None:
        thread = self._thread
        self._thread = None
        self._worker = None
        if thread is not None and thread.isRunning():
            thread.quit()
