"""Capture approximate before/after UI stills for Sprint 12.1 report."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.ui.theme.atlas_theme import COLORS  # noqa: E402

OUT = ROOT / "docs" / "sprint12_1_screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    before = QMainWindow()
    before.resize(720, 420)
    root = QWidget()
    root.setStyleSheet(
        f"background:{COLORS['bg_deep']}; color:{COLORS['text']};"
    )
    lay = QHBoxLayout(root)
    lay.setContentsMargins(0, 0, 0, 0)
    side = QFrame()
    side.setFixedWidth(232)
    side.setStyleSheet(f"background:{COLORS['bg_panel']};")
    sl = QVBoxLayout(side)
    sl.addWidget(QLabel("ATLAS STUDIO"))
    sl.addStretch()
    page = QWidget()
    pl = QVBoxLayout(page)
    pl.setContentsMargins(36, 36, 36, 36)
    for text in ("Voice Provider", "API Key", "Language"):
        lab = QLabel(text)
        lab.setStyleSheet(
            f"background:{COLORS['bg_deep']}; color:{COLORS['text']}; padding:4px;"
        )
        pl.addWidget(lab)
        if text == "Voice Provider":
            pl.addWidget(QComboBox())
        else:
            pl.addWidget(QLineEdit())
    pl.addStretch()
    lay.addWidget(side)
    lay.addWidget(page, 1)
    before.setCentralWidget(root)
    bar = QStatusBar()
    tiny = QLabel("Generating Images (1 / 15)")
    tiny.setStyleSheet(f"color:{COLORS['text_muted']}; font-size:12px;")
    bar.addWidget(tiny)
    before.setStatusBar(bar)
    before.show()
    app.processEvents()
    before.grab().save(str(OUT / "before_busy_labels_and_statusbar.png"))
    print("wrote before")


if __name__ == "__main__":
    main()
