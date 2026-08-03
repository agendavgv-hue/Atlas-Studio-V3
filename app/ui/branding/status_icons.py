"""Status indicator icons for project progress (no emoji)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

# Premium, restrained status colors
COLOR_COMPLETE = QColor("#3DAB6A")
COLOR_MISSING = QColor("#D45454")
COLOR_RUNNING = QColor("#D4B44A")
COLOR_RING = QColor("#2C333D")


def status_icon_pixmap(state: str, size: int = 18) -> QPixmap:
    """Draw a crisp status icon: complete | not_started | failed | running."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = 1.5
    rect_size = size - margin * 2
    key = (state or "").strip().casefold()
    if key in {"complete", "completed"}:
        _draw_complete(painter, margin, rect_size)
    elif key in {"running", "in_progress"}:
        _draw_running(painter, margin, rect_size, size)
    elif key in {"failed", "missing", "error"}:
        _draw_missing(painter, margin, rect_size, size)
    else:
        _draw_not_started(painter, margin, rect_size)

    painter.end()
    return pixmap


def _draw_not_started(painter: QPainter, margin: float, rect_size: float) -> None:
    """Empty ring — stage not started yet."""
    pen = QPen(COLOR_RING)
    pen.setWidthF(max(1.6, rect_size * 0.12))
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(int(margin + 1), int(margin + 1), int(rect_size - 2), int(rect_size - 2))


def _draw_complete(painter: QPainter, margin: float, rect_size: float) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(COLOR_COMPLETE)
    painter.drawEllipse(int(margin), int(margin), int(rect_size), int(rect_size))

    pen = QPen(QColor("#0B0D10"))
    pen.setWidthF(max(1.8, rect_size * 0.12))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    # Check mark
    x = margin + rect_size * 0.28
    y = margin + rect_size * 0.52
    painter.drawLine(
        int(x),
        int(y),
        int(margin + rect_size * 0.42),
        int(margin + rect_size * 0.68),
    )
    painter.drawLine(
        int(margin + rect_size * 0.42),
        int(margin + rect_size * 0.68),
        int(margin + rect_size * 0.72),
        int(margin + rect_size * 0.32),
    )


def _draw_missing(painter: QPainter, margin: float, rect_size: float, size: int) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(COLOR_MISSING)
    painter.drawEllipse(int(margin), int(margin), int(rect_size), int(rect_size))

    pen = QPen(QColor("#0B0D10"))
    pen.setWidthF(max(1.8, rect_size * 0.12))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    inset = rect_size * 0.30
    painter.drawLine(
        int(margin + inset),
        int(margin + inset),
        int(size - margin - inset),
        int(size - margin - inset),
    )
    painter.drawLine(
        int(size - margin - inset),
        int(margin + inset),
        int(margin + inset),
        int(size - margin - inset),
    )


def _draw_running(painter: QPainter, margin: float, rect_size: float, size: int) -> None:
    """Reserved for future Job Queue — yellow ring with center dot."""
    pen = QPen(COLOR_RUNNING)
    pen.setWidthF(max(2.0, rect_size * 0.14))
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(int(margin + 1), int(margin + 1), int(rect_size - 2), int(rect_size - 2))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(COLOR_RUNNING)
    dot = rect_size * 0.28
    painter.drawEllipse(
        int((size - dot) / 2),
        int((size - dot) / 2),
        int(dot),
        int(dot),
    )
