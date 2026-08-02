"""Reusable asset picker — browse, copy into channel folder, preview, remove."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.channels.studio.assets import is_image_path, is_video_path
from app.ui.pages.channel_studio.form_kit import help_button

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.svg *.webp);;All files (*.*)"
MEDIA_FILTER = (
    "Media (*.png *.jpg *.jpeg *.svg *.webp *.mp4);;"
    "Images (*.png *.jpg *.jpeg *.svg *.webp);;"
    "Video (*.mp4);;"
    "All files (*.*)"
)


class AssetPickerWidget(QWidget):
    """Asset card: preview + Browse / Replace / Remove / Open (no raw paths)."""

    changed = Signal(str)
    status_message = Signal(str)

    def __init__(
        self,
        *,
        title: str,
        asset_key: str,
        file_filter: str = IMAGE_FILTER,
        subdir: str = "branding",
        help_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._asset_key = asset_key
        self._filter = file_filter
        self._subdir = subdir
        self._folder = ""
        self._service = None
        self._stored = ""
        self._resolved: Path | None = None

        card = QFrame()
        card.setObjectName("StatusCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)

        head_row = QHBoxLayout()
        head = QLabel(title)
        head.setObjectName("SectionLabel")
        head_row.addWidget(head)
        head_row.addStretch()
        if help_text:
            head_row.addWidget(help_button(help_text))

        self._status = QLabel("Not set")
        self._status.setObjectName("PageSubtitle")

        self._preview = QLabel("Preview")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(110)
        self._preview.setMaximumHeight(140)
        self._preview.setStyleSheet(
            "QLabel { background: rgba(0,0,0,0.22); border-radius: 6px; }"
        )

        self._browse = QPushButton("Browse")
        self._browse.clicked.connect(self._pick)
        self._replace = QPushButton("Replace")
        self._replace.clicked.connect(self._pick)
        self._remove = QPushButton("Remove")
        self._remove.clicked.connect(self._remove_file)
        self._open = QPushButton("Open")
        self._open.clicked.connect(self._open_file)

        actions = QHBoxLayout()
        actions.addWidget(self._browse)
        actions.addWidget(self._replace)
        actions.addWidget(self._remove)
        actions.addWidget(self._open)
        actions.addStretch()

        card_layout.addLayout(head_row)
        card_layout.addWidget(self._status)
        card_layout.addWidget(self._preview)
        card_layout.addLayout(actions)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.addWidget(card)
        self._sync_actions()

    def bind(self, folder_name: str, service) -> None:
        self._folder = folder_name
        self._service = service
        self._refresh_preview()

    def set_stored_path(self, stored: str) -> None:
        self._stored = (stored or "").strip()
        self._refresh_preview()

    def stored_path(self) -> str:
        return self._stored

    def _pick(self) -> None:
        if not self._service or not self._folder:
            QMessageBox.information(
                self,
                self._title,
                "Open a channel in Channel Studio before selecting files.",
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select {self._title}", "", self._filter
        )
        if not path:
            return
        try:
            relative = self._service.install_asset(
                self._folder,
                self._asset_key,
                Path(path),
                subdir=self._subdir,
            )
        except (OSError, ValueError, FileNotFoundError) as exc:
            QMessageBox.warning(self, self._title, str(exc))
            return
        self._stored = relative
        self._refresh_preview()
        self.changed.emit(self._stored)
        self.status_message.emit(f"{self._title} updated")

    def _remove_file(self) -> None:
        if self._service and self._folder:
            try:
                self._service.remove_asset(
                    self._folder,
                    self._stored,
                    asset_key=self._asset_key,
                    subdir=self._subdir,
                )
            except OSError as exc:
                QMessageBox.warning(self, self._title, str(exc))
                return
        self._stored = ""
        self._refresh_preview()
        self.changed.emit("")
        self.status_message.emit(f"{self._title} removed")

    def _open_file(self) -> None:
        target = self._resolved
        if target is None or not target.is_file():
            QMessageBox.information(self, self._title, "No local file to open.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _sync_actions(self) -> None:
        has = bool(self._stored)
        self._browse.setVisible(not has)
        self._replace.setVisible(has)
        self._remove.setEnabled(has)
        self._open.setEnabled(has and self._resolved is not None)

    def _refresh_preview(self) -> None:
        self._resolved = None
        if not self._stored:
            self._status.setText("Not set")
            self._preview.setPixmap(QPixmap())
            self._preview.setText("Add a file")
            self._sync_actions()
            return

        if self._service and self._folder:
            self._resolved = self._service.resolve_asset(self._folder, self._stored)
        else:
            candidate = Path(self._stored)
            self._resolved = candidate if candidate.is_file() else None

        if self._resolved is None:
            self._status.setText("File missing — replace to restore")
            self._preview.setPixmap(QPixmap())
            self._preview.setText("Missing")
            self._sync_actions()
            return

        self._status.setText("Ready")
        if is_image_path(self._resolved):
            pix = QPixmap(str(self._resolved))
            if pix.isNull():
                self._preview.setPixmap(QPixmap())
                self._preview.setText(self._resolved.name)
            else:
                self._preview.setPixmap(
                    pix.scaled(
                        320,
                        120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        elif is_video_path(self._resolved):
            self._preview.setPixmap(QPixmap())
            self._preview.setText(f"Video ready\n{self._resolved.name}")
        else:
            self._preview.setPixmap(QPixmap())
            self._preview.setText(self._resolved.name)
        self._sync_actions()
