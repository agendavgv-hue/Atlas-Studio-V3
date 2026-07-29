"""Atlas Studio brand icons and logo pixmaps."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from app.ui.theme.atlas_theme import COLORS

_ASSETS = Path(__file__).resolve().parents[3] / "assets" / "branding"
_LOGO_PATH = _ASSETS / "Atlas_logo.png"
_ICON_PATH = _ASSETS / "atlas_icon.png"


def _paint_mark(pixmap: QPixmap) -> None:
    pixmap.fill(QColor(COLORS["bg_deep"]))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    size = pixmap.width()
    margin = int(size * 0.14)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(COLORS["bg_elevated"]))
    painter.drawRoundedRect(
        margin,
        margin,
        size - 2 * margin,
        size - 2 * margin,
        size * 0.18,
        size * 0.18,
    )

    painter.setPen(QColor(COLORS["accent"]))
    font = QFont("Segoe UI", int(size * 0.42), QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), "A")
    painter.end()


def logo_asset_path() -> Path:
    """Path to the primary Atlas logo asset."""
    return _LOGO_PATH


def _load_source_logo() -> QPixmap | None:
    if _LOGO_PATH.is_file():
        pixmap = QPixmap(str(_LOGO_PATH))
        if not pixmap.isNull():
            return pixmap
    return None


def create_logo_pixmap(size: int = 128) -> QPixmap:
    """Return the Atlas logo scaled to ``size`` (falls back to drawn mark)."""
    source = _load_source_logo()
    if source is not None:
        return source.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    pixmap = QPixmap(size, size)
    _paint_mark(pixmap)
    return pixmap


def ensure_icon_asset() -> Path:
    """Prefer Atlas_logo.png; keep a square icon file for the window/taskbar."""
    _ASSETS.mkdir(parents=True, exist_ok=True)
    if _LOGO_PATH.is_file():
        return _LOGO_PATH
    if not _ICON_PATH.is_file():
        create_logo_pixmap(256).save(str(_ICON_PATH), "PNG")
    return _ICON_PATH


def app_icon() -> QIcon:
    return QIcon(str(ensure_icon_asset()))
