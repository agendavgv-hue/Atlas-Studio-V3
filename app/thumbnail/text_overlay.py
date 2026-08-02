"""Atlas-rendered thumbnail headline overlay (not Stable Diffusion text)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRect
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen

from app.thumbnail.style_dna.layout import TextLayoutSpec, split_hook_lines


@dataclass(frozen=True)
class ThumbnailTextStyle:
    fill: QColor
    outline: QColor
    shadow: QColor
    align_left: bool = True
    max_width_ratio: float = 0.48
    top_ratio: float = 0.14
    max_lines: int = 3
    headline_scale: float = 1.0
    line_break_mode: str = "wrapped_phrase"
    draw_outline: bool = True
    draw_shadow: bool = True
    margin_x_ratio: float = 0.05
    use_soft_vignette: bool = True


def style_for_channel(
    channel_name: str,
    *,
    fill_hex: str = "",
    outline_hex: str = "",
    align_left: bool | None = None,
    layout: TextLayoutSpec | None = None,
) -> ThumbnailTextStyle:
    """Typography style from Brand Kit + learned Style DNA (never channel-hardcoded)."""
    _ = channel_name
    if layout is not None:
        return ThumbnailTextStyle(
            fill=QColor(fill_hex.strip() or "#FFF6D8"),
            outline=QColor(outline_hex.strip() or "#1A1208"),
            shadow=QColor(12, 8, 2, 220),
            align_left=layout.align_left if align_left is None else bool(align_left),
            max_width_ratio=layout.max_width_ratio,
            top_ratio=layout.top_ratio,
            max_lines=layout.max_lines,
            headline_scale=layout.headline_scale,
            line_break_mode=layout.line_break_mode,
            draw_outline=layout.outline,
            draw_shadow=layout.shadow,
            margin_x_ratio=layout.margin_x_ratio,
            use_soft_vignette=layout.use_soft_vignette,
        )
    return ThumbnailTextStyle(
        fill=QColor(fill_hex.strip() or "#FFF6D8"),
        outline=QColor(outline_hex.strip() or "#1A1208"),
        shadow=QColor(12, 8, 2, 220),
        align_left=True if align_left is None else bool(align_left),
    )


def render_thumbnail_text(
    image_png: bytes,
    hook: str,
    *,
    channel_name: str = "",
    fill_hex: str = "",
    outline_hex: str = "",
    font_family: str = "",
    align_left: bool | None = None,
    max_words: int = 0,
    layout: TextLayoutSpec | None = None,
) -> bytes:
    """Burn a professional hook onto the thumbnail PNG using Style DNA layout."""
    if not (hook or "").strip() or not image_png:
        return image_png

    image = QImage.fromData(image_png)
    if image.isNull():
        return image_png
    if image.format() != QImage.Format.Format_ARGB32:
        image = image.convertToFormat(QImage.Format.Format_ARGB32)

    style = style_for_channel(
        channel_name,
        fill_hex=fill_hex,
        outline_hex=outline_hex,
        align_left=align_left,
        layout=layout,
    )
    prepared = split_hook_lines(
        hook,
        max_words=max_words,
        max_lines=style.max_lines,
        line_break_mode=style.line_break_mode,
    )
    if not prepared:
        return image_png

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    width = image.width()
    height = image.height()
    max_text_width = int(width * style.max_width_ratio)
    margin_x = int(width * style.margin_x_ratio)
    top = int(height * style.top_ratio)

    if style.use_soft_vignette and style.align_left:
        _soft_left_readability(painter, width, height, max_text_width + margin_x * 2)
    elif style.use_soft_vignette and not style.align_left:
        _soft_right_readability(painter, width, height, max_text_width + margin_x * 2)

    family = (font_family or "").strip() or "Arial Black"
    font = QFont(family)
    if not font.exactMatch():
        font = QFont("Impact")
    if not font.exactMatch():
        font = QFont("Segoe UI Black")
    font.setBold(True)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

    # Base size from learned text height budget.
    point_size = max(28, int(height * min(0.18, 0.10 * style.headline_scale)))
    font.setPointSize(point_size)
    metrics = QFontMetrics(font)

    if len(prepared) == 1 and " " in prepared[0]:
        lines = _wrap_lines(
            prepared[0], metrics, max_text_width, max_lines=style.max_lines
        )
        while point_size > 22 and (
            any(metrics.horizontalAdvance(line) > max_text_width for line in lines)
            or metrics.height() * len(lines) > int(height * max(0.35, style.max_width_ratio))
        ):
            point_size -= 2
            font.setPointSize(point_size)
            metrics = QFontMetrics(font)
            lines = _wrap_lines(
                prepared[0], metrics, max_text_width, max_lines=style.max_lines
            )
    else:
        lines = prepared[: style.max_lines]
        while point_size > 22 and any(
            metrics.horizontalAdvance(line) > max_text_width for line in lines
        ):
            point_size -= 2
            font.setPointSize(point_size)
            metrics = QFontMetrics(font)

    y = top
    for index, line in enumerate(lines):
        line_font = QFont(font)
        if index == 0 and style.headline_scale > 1.05 and len(lines) > 1:
            scaled = max(point_size, int(point_size * style.headline_scale))
            line_font.setPointSize(scaled)
        line_metrics = QFontMetrics(line_font)
        line_width = line_metrics.horizontalAdvance(line)
        if style.align_left:
            x = margin_x
        elif style.max_width_ratio and not style.align_left:
            # Right column
            x = max(margin_x, width - margin_x - line_width)
        else:
            x = max(margin_x, (width - line_width) // 2)
        _draw_outlined_line(
            painter,
            line,
            x,
            y + line_metrics.ascent(),
            line_font,
            style,
        )
        y += line_metrics.height() + max(2, int(height * 0.008))

    painter.end()
    return _image_to_png_bytes(image)


def _wrap_lines(text: str, metrics: QFontMetrics, max_width: int, *, max_lines: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    remaining = words[1:]
    while remaining:
        word = remaining[0]
        trial = f"{current} {word}"
        if metrics.horizontalAdvance(trial) <= max_width:
            current = trial
            remaining = remaining[1:]
            continue
        lines.append(current)
        current = word
        remaining = remaining[1:]
        if len(lines) >= max_lines - 1:
            lines.append(" ".join([current, *remaining]).strip())
            return lines[:max_lines]
    lines.append(current)
    return lines[:max_lines]


def _draw_outlined_line(
    painter: QPainter,
    text: str,
    x: int,
    baseline_y: int,
    font: QFont,
    style: ThumbnailTextStyle,
) -> None:
    painter.setFont(font)
    if style.draw_shadow:
        painter.setPen(QPen(style.shadow))
        for dx, dy in ((6, 7), (4, 5), (3, 4), (2, 3)):
            painter.drawText(x + dx, baseline_y + dy, text)
    if style.draw_outline:
        painter.setPen(QPen(style.outline, 1))
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                if dx == 0 and dy == 0:
                    continue
                if abs(dx) + abs(dy) > 8:
                    continue
                painter.drawText(x + dx, baseline_y + dy, text)
    painter.setPen(QPen(style.fill))
    painter.drawText(x, baseline_y, text)


def _soft_left_readability(painter: QPainter, width: int, height: int, band: int) -> None:
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    for i in range(max(1, band)):
        alpha = int(70 * (1.0 - (i / band)))
        if alpha <= 0:
            break
        painter.fillRect(QRect(i, 0, 1, height), QColor(0, 0, 0, alpha))


def _soft_right_readability(painter: QPainter, width: int, height: int, band: int) -> None:
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    for i in range(max(1, band)):
        alpha = int(70 * (1.0 - (i / band)))
        if alpha <= 0:
            break
        painter.fillRect(QRect(width - 1 - i, 0, 1, height), QColor(0, 0, 0, alpha))


def _image_to_png_bytes(image: QImage) -> bytes:
    ba = QByteArray()
    buffer = QBuffer(ba)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(ba)
