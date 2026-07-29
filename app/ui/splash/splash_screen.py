"""Professional startup splash screen."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.ui.branding.icons import create_logo_pixmap
from app.ui.branding.identity import VERSION, WINDOW_TITLE
from app.ui.branding.status_icons import status_icon_pixmap
from app.ui.motion.fades import fade_window


class SplashScreen(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setObjectName("SplashScreen")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(420, 460)

        logo = QLabel()
        logo.setPixmap(create_logo_pixmap(120))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(WINDOW_TITLE)
        title.setObjectName("SplashTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version = QLabel(f"Version {VERSION}")
        version.setObjectName("SplashVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._status = QLabel("Initializing...")
        self._status.setObjectName("SplashStatus")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._steps_host = QWidget()
        self._steps_layout = QVBoxLayout(self._steps_host)
        self._steps_layout.setContentsMargins(24, 0, 24, 0)
        self._steps_layout.setSpacing(6)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 40, 36, 36)
        layout.setSpacing(10)
        layout.addStretch()
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addSpacing(18)
        layout.addWidget(self._status)
        layout.addWidget(self._steps_host)
        layout.addStretch()

    def show_centered(self) -> None:
        self.adjustSize()
        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )
        self.setWindowOpacity(0.0)
        self.show()
        fade_window(self, start=0.0, end=1.0, duration_ms=160)

    def mark_step(self, label: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        icon = QLabel()
        icon.setPixmap(status_icon_pixmap("complete", 14))
        icon.setFixedSize(16, 16)

        text = QLabel(label)
        text.setObjectName("SplashSteps")

        row_layout.addWidget(icon)
        row_layout.addWidget(text)
        row_layout.addStretch()
        self._steps_layout.addWidget(row)
        self._status.setText("Initializing...")

    def mark_ready(self) -> None:
        self._status.setText("Ready")

    def fade_out(self, finished) -> None:
        fade_window(self, start=1.0, end=0.0, duration_ms=160, finished=finished)
