"""First-run Chatterbox model download dialog (non-blocking worker)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import ai_storage
from app.providers.chatterbox_install import (
    CHATTERBOX_MODEL_SIZE_LABEL,
    ChatterboxModelMissingError,
    download_chatterbox_english,
    is_chatterbox_english_installed,
)


class _DownloadWorker(QObject):
    progress = Signal(int, int, str)  # downloaded, total, message
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, model_root: Path | None = None) -> None:
        super().__init__()
        self._root = model_root
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            path = download_chatterbox_english(
                self._root,
                on_progress=lambda done, total, msg: self.progress.emit(done, total, msg),
                cancel_check=lambda: self._cancel,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(str(path))


class ChatterboxModelDialog(QDialog):
    """Offer to download the Chatterbox model into the Atlas AI Models folder."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        model_root: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Chatterbox Model")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._root = model_root
        self._thread: QThread | None = None
        self._worker: _DownloadWorker | None = None
        self._succeeded = False

        directory = ai_storage.chatterbox_dir(model_root)

        title = QLabel("Chatterbox model not installed.")
        title.setObjectName("SectionLabel")

        body = QLabel(
            f"Model size:\n{CHATTERBOX_MODEL_SIZE_LABEL}\n\n"
            f"Download location:\n{directory}"
        )
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._status = QLabel("Ready to download.")
        self._status.setWordWrap(True)
        self._status.setObjectName("PageSubtitle")

        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.hide()

        self._download = QPushButton("Download")
        self._download.setObjectName("PrimaryButton")
        self._download.clicked.connect(self._start_download)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._buttons.rejected.connect(self.reject)
        close_btn = self._buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText("Close")

        actions = QHBoxLayout()
        actions.addWidget(self._download)
        actions.addStretch()
        actions.addWidget(self._buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addSpacing(8)
        layout.addWidget(self._status)
        layout.addWidget(self._progress)
        layout.addLayout(actions)

        if is_chatterbox_english_installed(model_root):
            self._status.setText("Chatterbox model is already installed.")
            self._download.setEnabled(False)
            self._succeeded = True

    @property
    def succeeded(self) -> bool:
        return self._succeeded and is_chatterbox_english_installed(self._root)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._request_cancel()
        super().closeEvent(event)

    def reject(self) -> None:
        self._request_cancel()
        super().reject()

    def _request_cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _start_download(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self._download.setEnabled(False)
        self._progress.show()
        self._progress.setValue(0)
        self._status.setText("Starting download…")

        worker = _DownloadWorker(self._root)
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
        self._worker = worker
        self._thread = thread
        thread.start()

    def _on_progress(self, downloaded: int, total: int, message: str) -> None:
        total = max(total, 1)
        self._progress.setValue(int(1000 * min(1.0, downloaded / total)))
        self._status.setText(message)

    def _on_finished(self, path: str) -> None:
        self._succeeded = True
        self._progress.setValue(1000)
        self._status.setText(f"Installed at {path}")
        self._download.setEnabled(False)
        self.accept()

    def _on_failed(self, message: str) -> None:
        self._succeeded = False
        self._status.setText(message)
        self._download.setEnabled(True)


def ensure_chatterbox_model(parent: QWidget | None = None) -> bool:
    """Return True when the English Chatterbox model is available (download if needed)."""
    ai_storage.apply_ai_storage_environment()
    if is_chatterbox_english_installed():
        return True
    dialog = ChatterboxModelDialog(parent)
    dialog.exec()
    return dialog.succeeded


def offer_chatterbox_download_for_error(
    parent: QWidget | None,
    error: BaseException,
) -> bool:
    """If ``error`` is a missing-model error, show the download dialog and return success."""
    if isinstance(error, ChatterboxModelMissingError):
        return ensure_chatterbox_model(parent)
    text = str(error).casefold()
    if "chatterbox model not installed" in text or "failed to load chatterbox" in text:
        if not is_chatterbox_english_installed():
            return ensure_chatterbox_model(parent)
    return False
