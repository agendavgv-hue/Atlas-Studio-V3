"""Application sidebar with brand mark and navigation."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


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

        logo = QLabel("ATLAS STUDIO")
        logo.setObjectName("SidebarLogo")

        tagline = QLabel("V3")
        tagline.setObjectName("SidebarTagline")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 16)
        layout.setSpacing(4)
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
