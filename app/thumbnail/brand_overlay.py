"""Post-AI brand overlays — logo and optional frame (never AI-generated)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter

from app.thumbnail.intelligence.branding import LogoPlacement


def apply_brand_overlays(
    image_png: bytes,
    *,
    logo_path: Path | None = None,
    frame_path: Path | None = None,
    placement: LogoPlacement | None = None,
) -> bytes:
    """Composite frame then logo onto the AI image. No text here."""
    if not image_png:
        return image_png
    image = QImage.fromData(image_png)
    if image.isNull():
        return image_png
    if image.format() != QImage.Format.Format_ARGB32:
        image = image.convertToFormat(QImage.Format.Format_ARGB32)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    if frame_path is not None and Path(frame_path).is_file():
        frame = QImage(str(frame_path))
        if not frame.isNull():
            painter.drawImage(image.rect(), frame)

    if logo_path is not None and Path(logo_path).is_file() and placement is not None:
        logo = QImage(str(logo_path))
        if not logo.isNull():
            _draw_logo(painter, image, logo, placement)

    painter.end()
    return _to_png(image)


def _draw_logo(
    painter: QPainter,
    canvas: QImage,
    logo: QImage,
    placement: LogoPlacement,
) -> None:
    w = canvas.width()
    h = canvas.height()
    target_w = max(24, int(w * float(placement.size)))
    scaled = logo.scaled(
        target_w,
        target_w,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    margin = int(placement.margin_px)
    pos = (placement.position or "bottom_left").casefold()
    x = margin
    y = margin
    if "right" in pos:
        x = w - scaled.width() - margin
    elif "center" in pos and "bottom" not in pos and "top" not in pos:
        x = (w - scaled.width()) // 2
    if "bottom" in pos:
        y = h - scaled.height() - margin
    elif "center" in pos and "left" not in pos and "right" not in pos:
        y = (h - scaled.height()) // 2
    elif "top" in pos:
        y = margin

    opacity = max(0.15, min(1.0, float(placement.opacity)))
    painter.setOpacity(opacity)
    painter.drawImage(x, y, scaled)
    painter.setOpacity(1.0)


def _to_png(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    data = bytes(QByteArray(buffer.data()))
    buffer.close()
    return data
