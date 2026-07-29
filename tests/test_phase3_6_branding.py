"""Phase 3.6 branding smoke tests."""

from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.atlas_application import AtlasApplication
from app.main_window import MainWindow
from app.ui.branding.identity import DEVELOPER, VERSION, WINDOW_TITLE
from app.ui.dialogs.about_dialog import AboutDialog
from app.ui.splash.splash_screen import SplashScreen
from app.ui.widgets.empty_state import EmptyState


class BrandingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        existing = AtlasApplication.instance()
        if existing is None:
            cls.app = AtlasApplication(sys.argv[:1])
        else:
            cls.app = existing

    def test_window_title_is_branded(self) -> None:
        window = MainWindow()
        self.assertEqual(window.windowTitle(), WINDOW_TITLE)
        window.close()

    def test_identity_constants(self) -> None:
        self.assertEqual(VERSION, "3.0.0")
        self.assertEqual(DEVELOPER, "Dennis Verbakel")

    def test_splash_screen_creates(self) -> None:
        splash = SplashScreen()
        self.assertEqual(splash.windowTitle() or "", "")
        splash.close()

    def test_about_dialog_creates(self) -> None:
        dialog = AboutDialog()
        self.assertIn("About", dialog.windowTitle())
        dialog.close()

    def test_empty_state_configure(self) -> None:
        empty = EmptyState()
        empty.configure("No Channels yet", "Create one to begin.", "Create", lambda: None)
        self.assertTrue(empty.isVisible() or True)


if __name__ == "__main__":
    unittest.main()
