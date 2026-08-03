"""Production asset card — identical actions for every tracked asset."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.projects.assets.models import AssetStatus, ProjectAsset
from app.ui.branding.status_icons import status_icon_pixmap


class ProductionAssetCard(QFrame):
    """One asset: Generate · Regenerate · Open · Reveal Folder."""

    generate_clicked = Signal(str)
    regenerate_clicked = Signal(str)
    open_clicked = Signal(str)
    reveal_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProductionCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._asset_id = ""
        self._stage_key = ""

        self._title = QLabel("ASSET")
        self._title.setObjectName("ProductionCardTitle")

        self._status_icon = QLabel()
        self._status_icon.setFixedSize(22, 22)
        self._status_text = QLabel("Not started")
        self._status_text.setObjectName("ProductionCardStatus")
        self._status_text.setWordWrap(True)

        self._meta = QLabel("")
        self._meta.setObjectName("PageSubtitle")
        self._meta.setWordWrap(True)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        status_row.addWidget(self._status_icon)
        status_row.addWidget(self._status_text, stretch=1)

        self._generate = QPushButton("Generate")
        self._generate.setObjectName("PrimaryButton")
        self._generate.clicked.connect(lambda: self.generate_clicked.emit(self._asset_id))

        self._open = QPushButton("Open")
        self._open.setObjectName("SecondaryButton")
        self._open.clicked.connect(lambda: self.open_clicked.emit(self._asset_id))

        self._reveal = QPushButton("Reveal Folder")
        self._reveal.setObjectName("SecondaryButton")
        self._reveal.clicked.connect(lambda: self.reveal_clicked.emit(self._asset_id))

        self._regenerate = QPushButton("Regenerate")
        self._regenerate.setObjectName("SecondaryButton")
        self._regenerate.clicked.connect(
            lambda: self.regenerate_clicked.emit(self._asset_id)
        )

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self._open)
        actions.addWidget(self._reveal)
        actions.addWidget(self._regenerate)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addWidget(self._title)
        layout.addLayout(status_row)
        layout.addWidget(self._meta)
        layout.addWidget(self._generate)
        layout.addLayout(actions)

    @property
    def asset_id(self) -> str:
        return self._asset_id

    @property
    def stage_key(self) -> str:
        return self._stage_key

    def apply_asset(self, asset: ProjectAsset, *, busy: bool = False) -> None:
        self._asset_id = asset.id
        self._stage_key = asset.stage_key
        self._title.setText(asset.label.upper())
        self._status_text.setText(asset.status.label)
        self._status_icon.setPixmap(status_icon_pixmap(asset.status.icon_state, 18))

        bits = [f"v{asset.version}"]
        if asset.generator:
            bits.append(asset.generator)
        if asset.location:
            bits.append(asset.location)
        if asset.updated_at:
            bits.append(asset.updated_at.replace("T", " ")[:16])
        self._meta.setText("  ·  ".join(bits))

        in_progress = asset.status is AssetStatus.IN_PROGRESS
        ready = asset.status.is_complete

        if in_progress:
            self._generate.setText("Working…")
            self._generate.setEnabled(False)
        else:
            self._generate.setText("Generate" if not ready else "Generate")
            self._generate.setEnabled(not busy)

        self._regenerate.setEnabled(not busy and ready and not in_progress)
        self._open.setEnabled(ready and bool(asset.location))
        self._reveal.setEnabled(bool(asset.location))
