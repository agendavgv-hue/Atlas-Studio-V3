"""Application bootstrap for Atlas Studio."""

from PySide6.QtWidgets import QApplication

from app.channels.channel_service import ChannelService
from app.core.storage import Storage, build_storage
from app.ui.theme.atlas_theme import apply_theme


class AtlasApplication(QApplication):
    """Owns application lifecycle, theme, storage, and channels."""

    storage: Storage
    channels: ChannelService

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setApplicationName("Atlas Studio")
        self.setOrganizationName("Atlas Studio")
        self.setStyle("Fusion")
        apply_theme(self)

        self.storage = build_storage()
        self.config = self.storage.config
        self.channels = ChannelService(self.storage, self.config)
