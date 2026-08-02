"""Lazy section host — placeholder until first visit, then cached content."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget


class LazySectionHost(QWidget):
    """Holds one Channel Studio tab with loading state and cached content."""

    def __init__(self, key: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.label = label
        self._content: QWidget | None = None

        self._loading = QLabel(f"Loading {label}…")
        self._loading.setObjectName("PageSubtitle")
        self._loading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._idle = QLabel(f"{label}\nOpen this tab to load its settings.")
        self._idle.setObjectName("PageSubtitle")
        self._idle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle.setWordWrap(True)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._idle)  # 0
        self._stack.addWidget(self._loading)  # 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    @property
    def content(self) -> QWidget | None:
        return self._content

    @property
    def is_ready(self) -> bool:
        return self._content is not None

    def show_idle(self) -> None:
        self._stack.setCurrentIndex(0)

    def show_loading(self) -> None:
        self._stack.setCurrentIndex(1)

    def set_content(self, widget: QWidget) -> None:
        if self._content is not None:
            self._stack.removeWidget(self._content)
            self._content.deleteLater()
        self._content = widget
        self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)

    def clear_content(self) -> None:
        if self._content is not None:
            self._stack.removeWidget(self._content)
            self._content.deleteLater()
            self._content = None
        self.show_idle()
