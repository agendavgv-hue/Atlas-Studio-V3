"""Dialog to move ``~/.cache/huggingface`` into the Atlas AI Models folder."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.core import ai_storage
from app.core.ai_storage import MigrationResult


class _MigrateWorker(QObject):
    progress = Signal(str, float)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, destination: Path) -> None:
        super().__init__()
        self._destination = destination

    def run(self) -> None:
        try:
            result = ai_storage.migrate_legacy_huggingface_cache(
                self._destination,
                on_progress=lambda msg, frac: self.progress.emit(msg, frac),
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(result)


class HuggingFaceMigrationDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        destination: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Move Hugging Face Cache")
        self.setModal(True)
        self.setMinimumWidth(460)
        self._destination = (destination or ai_storage.huggingface_dir()).resolve()
        self._result: MigrationResult | None = None
        self._thread: QThread | None = None

        src = ai_storage.legacy_huggingface_cache()
        intro = QLabel(
            "Models were found in the Windows default Hugging Face cache:\n\n"
            f"{src}\n\n"
            "Atlas can move them into your AI Models folder:\n\n"
            f"{self._destination}\n\n"
            "Future downloads will use the Atlas folder only."
        )
        intro.setWordWrap(True)

        self._status = QLabel("Click Move to begin.")
        self._status.setWordWrap(True)
        self._status.setObjectName("PageSubtitle")

        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Move")
        self._buttons.accepted.connect(self._start)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._status)
        layout.addWidget(self._progress)
        layout.addWidget(self._buttons)

    @property
    def result(self) -> MigrationResult | None:
        return self._result

    def _start(self) -> None:
        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok is not None:
            ok.setEnabled(False)
        if cancel is not None:
            cancel.setEnabled(False)

        worker = _MigrateWorker(self._destination)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished_ok.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished_ok.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def _on_progress(self, message: str, fraction: float) -> None:
        self._progress.setValue(int(1000 * max(0.0, min(1.0, fraction))))
        self._status.setText(message)

    def _on_finished(self, result: object) -> None:
        self._result = result if isinstance(result, MigrationResult) else None
        self._progress.setValue(1000)
        if self._result is not None:
            self._status.setText(
                f"Moved {self._result.moved} item(s), skipped {self._result.skipped}."
            )
        self.accept()

    def _on_failed(self, message: str) -> None:
        self._status.setText(message)
        QMessageBox.warning(self, "Atlas Studio", message)
        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok is not None:
            ok.setEnabled(True)
        if cancel is not None:
            cancel.setEnabled(True)


def offer_legacy_hf_migration(parent: QWidget | None = None) -> MigrationResult | None:
    """Ask to migrate when legacy cache has content and Atlas HF folder is empty-ish."""
    if not ai_storage.legacy_hf_cache_has_content():
        return None
    dest = ai_storage.huggingface_dir()
    # Offer whenever legacy content exists — user may still want to consolidate.
    answer = QMessageBox.question(
        parent,
        "Move AI Models",
        "Models were found in the Windows default Hugging Face cache:\n\n"
        f"{ai_storage.legacy_huggingface_cache()}\n\n"
        "Move them to the Atlas AI Models folder?\n\n"
        f"{dest}",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return None
    dialog = HuggingFaceMigrationDialog(parent, destination=dest)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.result
