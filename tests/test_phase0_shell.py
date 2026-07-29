"""Phase 0 smoke tests — launchable shell."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLabel

from app.atlas_application import AtlasApplication
from app.main_window import MainWindow
from app.ui.pages import ChannelsPage, DashboardPage, ProjectsPage, SettingsPage
from app.ui.sidebar import Sidebar


class Phase0ShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = AtlasApplication(sys.argv[:1])

    def test_main_window_creates(self) -> None:
        window = MainWindow()
        self.assertEqual(window.windowTitle(), "Atlas Studio V3")
        self.assertIsInstance(window._sidebar, Sidebar)
        window.close()

    def test_sidebar_logo_text(self) -> None:
        sidebar = Sidebar()
        logo_label = sidebar.findChild(QLabel, "SidebarLogo")
        self.assertIsNotNone(logo_label)
        assert logo_label is not None
        self.assertEqual(logo_label.text(), "ATLAS STUDIO")

    def test_navigation_switches_pages(self) -> None:
        window = MainWindow()
        self.assertEqual(window.current_page_key(), "dashboard")
        self.assertIsInstance(window._pages.currentWidget(), DashboardPage)

        window._show_page("channels")
        self.assertEqual(window.current_page_key(), "channels")
        self.assertIsInstance(window._pages.currentWidget(), ChannelsPage)

        window._show_page("projects")
        self.assertEqual(window.current_page_key(), "projects")
        self.assertIsInstance(window._pages.currentWidget(), ProjectsPage)

        window._show_page("settings")
        self.assertEqual(window.current_page_key(), "settings")
        self.assertIsInstance(window._pages.currentWidget(), SettingsPage)

        window.close()

    def test_nav_items_present(self) -> None:
        sidebar = Sidebar()
        keys = [key for key, _ in Sidebar.NAV_ITEMS]
        self.assertEqual(keys, ["dashboard", "channels", "projects", "settings"])
        for key in keys:
            self.assertIn(key, sidebar._buttons)


if __name__ == "__main__":
    unittest.main()
