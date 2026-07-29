"""Main application window shell."""

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from app.ui.pages import ChannelsPage, DashboardPage, ProjectsPage, SettingsPage
from app.ui.sidebar import Sidebar


class MainWindow(QMainWindow):
    """Shell hosting sidebar navigation and placeholder pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Atlas Studio")
        self.resize(1200, 760)
        self.setMinimumSize(900, 600)

        root = QWidget()
        self.setCentralWidget(root)

        self._sidebar = Sidebar()
        self._pages = QStackedWidget()

        self._page_index = {
            "dashboard": self._pages.addWidget(DashboardPage()),
            "channels": self._pages.addWidget(ChannelsPage()),
            "projects": self._pages.addWidget(ProjectsPage()),
            "settings": self._pages.addWidget(SettingsPage()),
        }

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._pages, stretch=1)

        self._sidebar.page_requested.connect(self._show_page)
        self._show_page("dashboard")

    def _show_page(self, key: str) -> None:
        index = self._page_index.get(key)
        if index is not None:
            self._pages.setCurrentIndex(index)
            self._sidebar.set_active(key)

    def current_page_key(self) -> str:
        current = self._pages.currentIndex()
        for key, index in self._page_index.items():
            if index == current:
                return key
        return "dashboard"
