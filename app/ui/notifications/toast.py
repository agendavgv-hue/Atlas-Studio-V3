"""Single toast notification."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from app.ui.motion.fades import fade_widget


class Toast(QFrame):
    closed = Signal(object)

    def __init__(self, title: str, message: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setFixedWidth(300)

        title_label = QLabel(title)
        title_label.setObjectName("ToastTitle")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        layout.addWidget(title_label)

        if message:
            message_label = QLabel(message)
            message_label.setObjectName("ToastMessage")
            message_label.setWordWrap(True)
            layout.addWidget(message_label)

        self.setWindowOpacity(0.0)
        fade_widget(self, start=0.0, end=1.0, duration_ms=150)
        QTimer.singleShot(2800, self._begin_close)

    def _begin_close(self) -> None:
        fade_widget(self, start=1.0, end=0.0, duration_ms=150, finished=self._finish)

    def _finish(self) -> None:
        self.closed.emit(self)
        self.deleteLater()
