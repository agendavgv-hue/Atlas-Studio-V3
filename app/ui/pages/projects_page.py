"""Projects placeholder page."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ProjectsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Projects")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Projects will appear here.")
        subtitle.setObjectName("PageSubtitle")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
