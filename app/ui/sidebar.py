"""Application sidebar with brand mark, navigation, and live Status card."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.branding.icons import create_logo_pixmap
from app.ui.widgets.forge_status_indicator import ForgeStatusIndicator
from app.ui.widgets.status_card import StatusCard


class Sidebar(QFrame):
    """Left navigation rail for Atlas Studio."""

    page_requested = Signal(str)
    about_requested = Signal()
    forge_settings_requested = Signal()
    forge_action_requested = Signal(str)

    NAV_ITEMS = (
        ("dashboard", "Dashboard"),
        ("channels", "Channels"),
        ("channel_studio", "Channel Studio"),
        ("projects", "Projects"),
        ("thumbnail_review", "Thumbnail Review"),
        ("design_review", "Design Review"),
        ("ai_providers", "AI Providers"),
        ("settings", "Settings"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(268)

        brand = QWidget()
        brand.setObjectName("SidebarBrand")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(20, 20, 20, 16)
        brand_layout.setSpacing(10)

        logo_image = QLabel()
        logo_image.setObjectName("SidebarLogoImage")
        logo_image.setPixmap(create_logo_pixmap(72))
        logo_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QLabel("ATLAS STUDIO")
        logo.setObjectName("SidebarLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline = QLabel("V3")
        tagline.setObjectName("SidebarTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        brand_layout.addWidget(logo_image)
        brand_layout.addWidget(logo)
        brand_layout.addWidget(tagline)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(6)
        layout.addWidget(brand)

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

        layout.addSpacing(10)
        self._status_card = StatusCard()
        layout.addWidget(self._status_card)
        layout.addStretch(1)

        self._forge_status = ForgeStatusIndicator()
        self._forge_status.clicked.connect(self.forge_settings_requested.emit)
        self._forge_status.action_requested.connect(self.forge_action_requested.emit)
        layout.addWidget(self._forge_status)

        about = QPushButton("About")
        about.setProperty("navButton", True)
        about.clicked.connect(self.about_requested.emit)
        layout.addWidget(about)

        self.set_active("dashboard")

    @property
    def status_card(self) -> StatusCard:
        return self._status_card

    @property
    def forge_status(self) -> ForgeStatusIndicator:
        return self._forge_status

    def _on_nav(self, key: str) -> None:
        self.set_active(key)
        self.page_requested.emit(key)

    def set_active(self, key: str) -> None:
        for nav_key, button in self._buttons.items():
            button.setChecked(nav_key == key)
            button.style().unpolish(button)
            button.style().polish(button)
