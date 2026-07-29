"""Application sidebar with brand mark and navigation."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.branding.icons import create_logo_pixmap


class Sidebar(QFrame):
    """Left navigation rail for Atlas Studio."""

    page_requested = Signal(str)
    about_requested = Signal()

    NAV_ITEMS = (
        ("dashboard", "Dashboard"),
        ("channels", "Channels"),
        ("projects", "Projects"),
        ("settings", "Settings"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(228)

        logo_image = QLabel()
        logo_image.setObjectName("SidebarLogoImage")
        logo_image.setPixmap(create_logo_pixmap(56))
        logo_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QLabel("ATLAS STUDIO")
        logo.setObjectName("SidebarLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline = QLabel("V3")
        tagline.setObjectName("SidebarTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 16)
        layout.setSpacing(2)
        layout.addWidget(logo_image)
        layout.addWidget(logo)
        layout.addWidget(tagline)

        self._buttons: dict[str, QPushButton] = {}
        for key, label in self.NAV_ITEMS:
            button = QPushButton(label)
            button.setObjectName(f"Nav_{key}")
            button.setProperty("navButton", True)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(lambda checked=False, k=key: self._on_nav(k))
            self._buttons[key] = button
            layout.addWidget(button)

        layout.addStretch()

        about = QPushButton("About")
        about.setProperty("navButton", True)
        about.clicked.connect(self.about_requested.emit)
        layout.addWidget(about)

        self.set_active("dashboard")

    def _on_nav(self, key: str) -> None:
        self.set_active(key)
        self.page_requested.emit(key)

    def set_active(self, key: str) -> None:
        for nav_key, button in self._buttons.items():
            button.setChecked(nav_key == key)
            button.style().unpolish(button)
            button.style().polish(button)
