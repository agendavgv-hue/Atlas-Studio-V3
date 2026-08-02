"""Reusable reference library panel for Channel Studio sections."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ReferencePanel(QWidget):
    """Upload / preview / replace / delete references for one kind."""

    changed = Signal()
    status_message = Signal(str)

    def __init__(
        self,
        *,
        kind: str,
        title: str,
        max_count: int = 20,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._max = max_count
        self._folder = ""
        self._loader = None  # set via bind()
        self.setAcceptDrops(True)

        head = QLabel(title)
        head.setObjectName("SectionLabel")
        self._count = QLabel(f"0 / {max_count}")
        self._count.setObjectName("PageSubtitle")
        self._list = QListWidget()
        self._list.setMinimumHeight(110)
        self._list.currentItemChanged.connect(self._preview)
        self._preview_label = QLabel("Preview — drop files here or use Upload")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(120)
        self._preview_label.setStyleSheet(
            "QLabel { background: rgba(0,0,0,0.22); border-radius: 6px; }"
        )

        upload = QPushButton("Upload…")
        upload.clicked.connect(self._upload)
        replace = QPushButton("Replace…")
        replace.clicked.connect(self._replace)
        delete = QPushButton("Delete")
        delete.clicked.connect(self._delete)
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self._open)
        row = QHBoxLayout()
        row.addWidget(upload)
        row.addWidget(replace)
        row.addWidget(delete)
        row.addWidget(open_btn)
        row.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(head)
        layout.addWidget(self._count)
        layout.addWidget(self._list)
        layout.addWidget(self._preview_label)
        layout.addLayout(row)

    def bind(self, folder_name: str, service) -> None:
        self._folder = folder_name
        self._loader = service
        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        if not self._loader or not self._folder:
            self._count.setText(f"0 / {self._max}")
            return
        files = self._loader.list_references(self._folder, self._kind)
        for path in files:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self._list.addItem(item)
        self._count.setText(f"{len(files)} / {self._max}")

    def _selected(self) -> Path | None:
        item = self._list.currentItem()
        if not item:
            return None
        return Path(str(item.data(Qt.ItemDataRole.UserRole) or ""))

    def _preview(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText("Preview")
            return
        path = Path(str(current.data(Qt.ItemDataRole.UserRole) or ""))
        pix = QPixmap(str(path))
        if pix.isNull():
            self._preview_label.setText(path.name)
            return
        self._preview_label.setPixmap(
            pix.scaled(
                280,
                120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _upload(self) -> None:
        if not self._loader or not self._folder:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Upload references",
            "",
            "Media (*.png *.jpg *.jpeg *.webp *.gif *.bmp *.mp4 *.wav *.mp3)",
        )
        if not paths:
            return
        existing = len(self._loader.list_references(self._folder, self._kind))
        for raw in paths:
            if existing >= self._max:
                QMessageBox.warning(
                    self, "Channel Studio", f"Maximum of {self._max} references reached."
                )
                break
            try:
                self._loader.add_reference(self._folder, self._kind, Path(raw))
                existing += 1
            except OSError as exc:
                QMessageBox.warning(self, "Channel Studio", str(exc))
                break
        self.refresh()
        self.changed.emit()
        self.status_message.emit(f"Updated {self._kind} references")

    def _replace(self) -> None:
        target = self._selected()
        if not target or not self._loader or not self._folder:
            QMessageBox.information(self, "Channel Studio", "Select a reference to replace.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Replace reference",
            "",
            "Media (*.png *.jpg *.jpeg *.webp *.gif *.bmp *.mp4 *.wav *.mp3)",
        )
        if not path:
            return
        try:
            self._loader.delete_reference(self._folder, self._kind, target)
            self._loader.add_reference(self._folder, self._kind, Path(path))
        except (OSError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Channel Studio", str(exc))
            return
        self.refresh()
        self.changed.emit()
        self.status_message.emit(f"Replaced {self._kind} reference")

    def _delete(self) -> None:
        target = self._selected()
        if not target or not self._loader:
            return
        try:
            self._loader.delete_reference(self._folder, self._kind, target)
        except (OSError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Channel Studio", str(exc))
            return
        self.refresh()
        self.changed.emit()

    def _open(self) -> None:
        target = self._selected()
        if target and target.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if not self._loader or not self._folder:
            return
        existing = len(self._loader.list_references(self._folder, self._kind))
        for url in event.mimeData().urls():
            if existing >= self._max:
                QMessageBox.warning(
                    self, "Channel Studio", f"Maximum of {self._max} references reached."
                )
                break
            path = Path(url.toLocalFile())
            if not path.is_file():
                continue
            try:
                self._loader.add_reference(self._folder, self._kind, path)
                existing += 1
            except OSError as exc:
                QMessageBox.warning(self, "Channel Studio", str(exc))
                break
        self.refresh()
        self.changed.emit()
        self.status_message.emit(f"Updated {self._kind} references")
        event.acceptProposedAction()
