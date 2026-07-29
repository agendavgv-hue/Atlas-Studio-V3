"""Reusable empty-state panel."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class EmptyState(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EmptyState")

        self._title = QLabel("")
        self._title.setObjectName("EmptyStateTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._message = QLabel("")
        self._message.setObjectName("EmptyStateMessage")
        self._message.setWordWrap(True)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._button = QPushButton("")
        self._button.setObjectName("PrimaryButton")
        self._button.hide()
        self._action: Callable[[], None] | None = None
        self._button.clicked.connect(self._emit_action)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 48, 40, 48)
        layout.setSpacing(12)
        layout.addStretch()
        layout.addWidget(self._title)
        layout.addWidget(self._message)
        layout.addSpacing(8)
        layout.addWidget(self._button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def configure(
        self,
        title: str,
        message: str,
        action_label: str | None = None,
        on_action: Callable[[], None] | None = None,
    ) -> None:
        self._title.setText(title)
        self._message.setText(message)
        self._action = on_action
        if action_label and on_action is not None:
            self._button.setText(action_label)
            self._button.show()
        else:
            self._button.hide()

    def _emit_action(self) -> None:
        if self._action is not None:
            self._action()
