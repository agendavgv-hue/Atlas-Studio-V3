"""Dashboard welcome page."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.branding.identity import APP_NAME, VERSION
from app.ui.widgets.empty_state import EmptyState


class DashboardPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")

        subtitle = QLabel(f"{APP_NAME} {VERSION}")
        subtitle.setObjectName("PageSubtitle")

        empty = EmptyState()
        empty.configure(
            "Welcome to Atlas Studio",
            "Select a channel, create a project, and produce through one clear workflow.",
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(empty, stretch=1)
