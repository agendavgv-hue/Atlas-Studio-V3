"""Channels placeholder page."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ChannelsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Channels")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Channel management will appear here.")
        subtitle.setObjectName("PageSubtitle")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
