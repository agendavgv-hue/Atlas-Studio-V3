"""Application bootstrap for Atlas Studio."""

from PySide6.QtWidgets import QApplication

from app.ui.theme.atlas_theme import apply_theme


class AtlasApplication(QApplication):
    """Owns application lifecycle and global theme."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setApplicationName("Atlas Studio")
        self.setOrganizationName("Atlas Studio")
        self.setStyle("Fusion")
        apply_theme(self)
