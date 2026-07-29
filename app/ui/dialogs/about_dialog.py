"""About dialog for Atlas Studio."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.branding.icons import create_logo_pixmap
from app.ui.branding.identity import (
    APP_NAME,
    ARCHITECTURE,
    DEVELOPER,
    VERSION,
)


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setModal(True)
        self.setFixedWidth(360)

        logo = QLabel()
        logo.setPixmap(create_logo_pixmap(96))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name = QLabel(APP_NAME)
        name.setObjectName("PageTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version = QLabel(f"Version {VERSION}")
        version.setObjectName("PageSubtitle")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        developer = QLabel(f"Developer: {DEVELOPER}")
        developer.setObjectName("PageSubtitle")
        developer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        architecture = QLabel(f"Architecture: {ARCHITECTURE}")
        architecture.setObjectName("PageSubtitle")
        architecture.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_button = QPushButton("Close")
        close_button.setObjectName("PrimaryButton")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(10)
        layout.addWidget(logo)
        layout.addWidget(name)
        layout.addWidget(version)
        layout.addSpacing(8)
        layout.addWidget(developer)
        layout.addWidget(architecture)
        layout.addSpacing(16)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignCenter)
