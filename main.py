"""Atlas Studio V3 entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import QElapsedTimer, QEventLoop, QTimer

from app.atlas_application import AtlasApplication
from app.main_window import MainWindow
from app.ui.splash.splash_screen import SplashScreen

# Minimum branding visibility — bootstrap still starts immediately.
_MIN_SPLASH_MS = 3000


def main() -> int:
    app = AtlasApplication(sys.argv, auto_bootstrap=False)

    splash = SplashScreen()
    splash.show_centered()
    app.processEvents()

    timer = QElapsedTimer()
    timer.start()

    def on_step(label: str) -> None:
        splash.mark_step(label)
        app.processEvents()

    app.bootstrap(on_step)
    splash.mark_ready()
    app.processEvents()

    remaining = _MIN_SPLASH_MS - timer.elapsed()
    if remaining > 0:
        wait = QEventLoop()
        QTimer.singleShot(remaining, wait.quit)
        wait.exec()

    window = MainWindow()
    window.setWindowIcon(app.windowIcon())

    loop = QEventLoop()
    splash.fade_out(loop.quit)
    loop.exec()
    splash.close()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
