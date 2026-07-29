"""Dashboard welcome page."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.branding.identity import WINDOW_TITLE, VERSION


class DashboardPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")

        subtitle = QLabel(f"{WINDOW_TITLE}  ·  Version {VERSION}")
        subtitle.setObjectName("PageSubtitle")

        welcome = QLabel("Welcome to Atlas Studio")
        welcome.setObjectName("WelcomeTitle")

        message = QLabel(
            "Select a channel, create a project, and produce through one clear workflow."
        )
        message.setObjectName("PageSubtitle")
        message.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(28)
        layout.addWidget(welcome)
        layout.addWidget(message)
        layout.addStretch()
