"""Render a layout candidate onto the AI illustration."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen

from app.thumbnail.brand_overlay import apply_brand_overlays
from app.thumbnail.design_engine.models import LayoutCandidate
from app.thumbnail.intelligence.branding import LogoPlacement
from app.thumbnail.pipeline.brand_composer import BrandComposerAssets


_SCALE = {"small": 0.85, "medium": 1.0, "large": 1.18}


def render_layout(
    illustration_png: bytes,
    layout: LayoutCandidate,
    *,
    assets: BrandComposerAssets,
    channel_name: str = "",
) -> bytes:
    """Frame + logo from Brand Kit/DNA, typography from layout candidate."""
    del channel_name
    placement = LogoPlacement(
        position=layout.logo_position,
        size=float(layout.logo_scale),
        opacity=float(assets.placement.opacity) if assets.placement else 0.92,
        margin_px=int(assets.placement.margin_px) if assets.placement else 48,
        auto_scaled=True,
        reason="design_engine",
    )
    base = apply_brand_overlays(
        illustration_png,
        logo_path=assets.logo_path,
        frame_path=assets.frame_path,
        placement=placement if assets.logo_path else None,
    )
    return _paint_text(
        base,
        layout,
        fill_hex=assets.fill_hex,
        outline_hex=assets.outline_hex,
        font_family=assets.font_family,
        outline=True if assets.text_layout is None else assets.text_layout.outline,
        shadow=True if assets.text_layout is None else assets.text_layout.shadow,
    )


def _paint_text(
    image_png: bytes,
    layout: LayoutCandidate,
    *,
    fill_hex: str,
    outline_hex: str,
    font_family: str,
    outline: bool,
    shadow: bool,
) -> bytes:
    if not layout.lines or not image_png:
        return image_png
    image = QImage.fromData(image_png)
    if image.isNull():
        return image_png
    if image.format() != QImage.Format.Format_ARGB32:
        image = image.convertToFormat(QImage.Format.Format_ARGB32)

    width = image.width()
    height = image.height()
    margin_x = int(width * layout.margin_x_ratio)
    max_text_w = int(width * layout.max_width_ratio)
    top = int(height * layout.top_ratio)
    fill = QColor(fill_hex.strip() or "#FFF6D8")
    outline_c = QColor(outline_hex.strip() or "#1A1208")
    shadow_c = QColor(12, 8, 2, 220)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    if layout.text_anchor == "left":
        _vignette(painter, width, height, max_text_w + margin_x * 2, side="left")
    elif layout.text_anchor == "right":
        _vignette(painter, width, height, max_text_w + margin_x * 2, side="right")

    family = (font_family or "").strip() or "Arial Black"
    font = QFont(family)
    if not font.exactMatch():
        font = QFont("Impact")
    if not font.exactMatch():
        font = QFont("Segoe UI Black")
    font.setBold(True)

    mult = _SCALE.get(layout.title_scale, 1.0)
    point = max(22, int(height * 0.11 * mult))
    font.setPointSize(point)
    metrics = QFontMetrics(font)
    while point > 18 and any(
        metrics.horizontalAdvance(line) > max_text_w for line in layout.lines
    ):
        point -= 2
        font.setPointSize(point)
        metrics = QFontMetrics(font)

    y = top
    for index, line in enumerate(layout.lines):
        line_font = QFont(font)
        if index == 0 and layout.title_scale == "large" and len(layout.lines) > 1:
            line_font.setPointSize(max(point, int(point * 1.25)))
        elif index == 1 and len(layout.lines) == 3:
            line_font.setPointSize(max(point, int(point * 1.35)))
        lm = QFontMetrics(line_font)
        lw = lm.horizontalAdvance(line)
        if layout.text_align == "left":
            x = margin_x
        elif layout.text_align == "right":
            x = max(margin_x, width - margin_x - lw)
        else:
            x = max(margin_x, (width - lw) // 2)
        _draw_line(
            painter,
            line,
            x,
            y + lm.ascent(),
            line_font,
            fill=fill,
            outline=outline_c,
            shadow=shadow_c,
            draw_outline=outline,
            draw_shadow=shadow,
        )
        y += lm.height() + max(2, int(height * 0.008))

    painter.end()
    return _to_png(image)


def _draw_line(
    painter: QPainter,
    text: str,
    x: int,
    baseline: int,
    font: QFont,
    *,
    fill: QColor,
    outline: QColor,
    shadow: QColor,
    draw_outline: bool,
    draw_shadow: bool,
) -> None:
    painter.setFont(font)
    if draw_shadow:
        painter.setPen(QPen(shadow))
        for dx, dy in ((6, 7), (4, 5), (3, 4)):
            painter.drawText(x + dx, baseline + dy, text)
    if draw_outline:
        painter.setPen(QPen(outline, 1))
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                if dx or dy:
                    painter.drawText(x + dx, baseline + dy, text)
    painter.setPen(QPen(fill))
    painter.drawText(x, baseline, text)


def _vignette(
    painter: QPainter, width: int, height: int, band: int, *, side: str
) -> None:
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    for i in range(max(1, band)):
        alpha = int(70 * (1.0 - (i / band)))
        if alpha <= 0:
            break
        x = i if side == "left" else width - 1 - i
        painter.fillRect(QRect(x, 0, 1, height), QColor(0, 0, 0, alpha))


def _to_png(image: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def save_layout_preview(path: Path, png: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return path
