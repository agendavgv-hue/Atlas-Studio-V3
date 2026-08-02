"""Style DNA debug card for Channel Studio Thumbnail tab."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.thumbnail.style_dna.models import ThumbnailStyleDNA
from app.thumbnail.style_dna.service import ThumbnailStyleDNAService


class StyleDNACard(QFrame):
    """Visual debug of learned thumbnail Style DNA."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusCard")
        self._data_root: Path | None = None
        self._folder = ""

        title = QLabel("STYLE DNA")
        title.setObjectName("SectionLabel")
        self._subtitle = QLabel("Upload reference thumbnails to learn this channel’s layout.")
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(18)
        self._grid.setVerticalSpacing(6)
        self._value_labels: list[QLabel] = []

        self._rebuild = QPushButton("Re-analyze Style DNA")
        self._rebuild.clicked.connect(self.rebuild)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(self._subtitle)
        layout.addLayout(self._grid)
        layout.addWidget(self._rebuild, alignment=Qt.AlignmentFlag.AlignLeft)

        self.clear()

    def bind(self, data_root: Path, folder_name: str) -> None:
        self._data_root = Path(data_root)
        self._folder = folder_name
        self.refresh()

    def clear(self) -> None:
        self._set_rows(
            [
                ("Text Layout", "—"),
                ("Headline Scale", "—"),
                ("Logo", "—"),
                ("Negative Space", "—"),
                ("Subject", "—"),
                ("References", "0"),
            ]
        )
        self._subtitle.setText(
            "Upload reference thumbnails to learn this channel’s layout."
        )

    def refresh(self) -> None:
        if self._data_root is None or not self._folder:
            self.clear()
            return
        dna = ThumbnailStyleDNAService(self._data_root).load(self._folder)
        if dna is None:
            self.clear()
            return
        self.show_dna(dna)

    def rebuild(self) -> None:
        if self._data_root is None or not self._folder:
            return
        dna = ThumbnailStyleDNAService(self._data_root).ensure(
            self._folder, force=True
        )
        self.show_dna(dna)

    def show_dna(
        self,
        dna: ThumbnailStyleDNA,
        *,
        similarity: float | None = None,
        brand_consistency: float | None = None,
    ) -> None:
        rows = list(dna.debug_rows())
        if similarity is not None:
            rows.append(("Similarity", f"{similarity:.0f}%"))
        if brand_consistency is not None:
            rows.append(("Brand Consistency", f"{brand_consistency:.0f}%"))
        self._set_rows(rows)
        self._subtitle.setText(
            f"Learned from {dna.reference_count} reference thumbnail(s) · "
            f"{dna.line_break_mode.replace('_', ' ')} · {dna.brand_style.replace('_', ' ')}"
        )

    def _set_rows(self, rows: list[tuple[str, str]]) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._value_labels.clear()
        for i, (label, value) in enumerate(rows):
            key = QLabel(label)
            key.setObjectName("PageSubtitle")
            val = QLabel(str(value))
            val.setObjectName("SectionLabel")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._grid.addWidget(key, i, 0)
            self._grid.addWidget(val, i, 1)
            self._value_labels.append(val)
