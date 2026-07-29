"""Reusable project progress row with painted status icons."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.ui.branding.status_icons import status_icon_pixmap


class ProgressRow(QWidget):
    def __init__(self, label: str, state: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProgressRow")

        icon = QLabel()
        icon.setObjectName("ProgressIcon")
        icon.setPixmap(status_icon_pixmap(state, 18))
        icon.setFixedSize(22, 22)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text = QLabel(label)
        text.setObjectName("ProgressLabel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        layout.addWidget(icon)
        layout.addWidget(text, stretch=1)
