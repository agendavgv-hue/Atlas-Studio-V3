"""Geometric analysis of one complete YouTube thumbnail reference."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from PySide6.QtGui import QColor, QImage

from app.thumbnail.style_dna.models import ReferenceStyleSample

_WORK_W = 320
_WORK_H = 180


def analyze_reference_geometry(path: Path) -> ReferenceStyleSample | None:
    """Measure text band, logo corner, subject side, and margins from pixels."""
    image = QImage(str(path))
    if image.isNull():
        return None
    sample = image.scaled(_WORK_W, _WORK_H)
    w, h = sample.width(), sample.height()
    if w < 8 or h < 8:
        return None

    # Luma + "text-like" mask (bright / high-contrast / yellow-white headline paint)
    luma = [[0.0] * w for _ in range(h)]
    text_mask = [[0] * w for _ in range(h)]
    sat_mask = [[0] * w for _ in range(h)]
    colors: Counter[str] = Counter()

    for y in range(h):
        for x in range(w):
            c = QColor(sample.pixel(x, y))
            r, g, b = c.red(), c.green(), c.blue()
            L = 0.2126 * r + 0.7152 * g + 0.0722 * b
            luma[y][x] = L
            qr, qg, qb = (r // 32) * 32, (g // 32) * 32, (b // 32) * 32
            colors[f"#{qr:02x}{qg:02x}{qb:02x}"] += 1
            mx = max(r, g, b)
            mn = min(r, g, b)
            sat = (mx - mn) / 255.0
            # Headline paint: bright and/or warm yellow cream with strong local contrast.
            if L >= 170 or (L >= 140 and sat >= 0.25 and r >= g >= b * 0.7):
                text_mask[y][x] = 1
            if sat >= 0.35 and L >= 40:
                sat_mask[y][x] = 1

    # Local contrast boost for text mask
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if abs(luma[y][x] - luma[y][x - 1]) > 55 and luma[y][x] > 120:
                text_mask[y][x] = 1

    row_density = [sum(text_mask[y]) / w for y in range(h)]
    # Smooth rows
    smooth = []
    for y in range(h):
        a = row_density[max(0, y - 1)]
        b = row_density[y]
        c = row_density[min(h - 1, y + 1)]
        smooth.append((a + b + c) / 3.0)

    threshold = max(0.035, sorted(smooth)[int(h * 0.72)] if h else 0.05)
    bands = _find_bands(smooth, threshold)
    if not bands:
        # Fallback: upper-left third as text region for dark documentary thumbs.
        bands = [(int(h * 0.10), int(h * 0.42))]

    text_top = bands[0][0] / h
    text_bottom = bands[-1][1] / h
    text_height = max(0.12, min(0.75, text_bottom - text_top))
    text_lines = max(1, min(6, len(bands)))

    # Horizontal extent of text within band rows
    col_hits = [0] * w
    y0, y1 = bands[0][0], bands[-1][1]
    for y in range(y0, min(h, y1 + 1)):
        for x in range(w):
            if text_mask[y][x]:
                col_hits[x] += 1
    active_cols = [i for i, v in enumerate(col_hits) if v > (y1 - y0 + 1) * 0.08]
    if active_cols:
        left_x = active_cols[0] / w
        right_x = (active_cols[-1] + 1) / w
    else:
        left_x, right_x = 0.04, 0.42
    text_width = max(0.18, min(0.62, right_x - left_x))
    text_mid = (left_x + right_x) / 2.0
    if text_mid < 0.40:
        text_position = "left"
        text_alignment = "left"
        negative_space = "left"
        subject_position = "right"
    elif text_mid > 0.60:
        text_position = "right"
        text_alignment = "right"
        negative_space = "right"
        subject_position = "left"
    else:
        text_position = "center"
        text_alignment = "center"
        negative_space = "top"
        subject_position = "center"

    # Headline scale: tallest band vs median band height
    band_heights = [(b1 - b0 + 1) for b0, b1 in bands]
    median_h = sorted(band_heights)[len(band_heights) // 2]
    tallest = max(band_heights)
    headline_scale = round(max(1.0, min(2.6, tallest / max(1, median_h))), 3)
    # Short wide-ish bands vs tall narrow → stacked single words
    avg_band_h = sum(band_heights) / len(band_heights)
    stacked_hint = text_lines >= 2 and (avg_band_h / h) >= 0.09 and text_width <= 0.48

    # Logo: scan four corners for saturated compact blobs
    logo_position, logo_scale, logo_margin = _detect_logo(sat_mask, luma, w, h)

    # Subject focus: opposite of text, high edge energy
    focus_x, focus_y, balance = _detect_focus(luma, text_position, w, h)
    if subject_position == "center":
        subject_position = "right" if focus_x >= 0.5 else "left"

    # Outline/shadow likelihood near text mask edges
    outline_likely, shadow_likely = _outline_shadow_likelihood(text_mask, luma, w, h)

    # Rule of thirds: focus near thirds lines
    thirds = (abs(focus_x - 1 / 3) < 0.12) or (abs(focus_x - 2 / 3) < 0.12)
    thirds = thirds or (abs(focus_y - 1 / 3) < 0.12) or (abs(focus_y - 2 / 3) < 0.12)

    coverage = max(0.15, min(0.7, text_width * text_height * 1.15))
    notes = []
    if stacked_hint:
        notes.append("stacked_word_lines_detected")
    notes.append(f"bands={text_lines}")

    return ReferenceStyleSample(
        path=str(path),
        text_position=text_position,
        text_alignment=text_alignment,
        text_top=round(text_top, 4),
        text_height=round(text_height, 4),
        text_width=round(text_width, 4),
        text_lines=text_lines,
        text_coverage=round(coverage, 4),
        headline_scale=headline_scale,
        outline_likely=outline_likely,
        shadow_likely=shadow_likely,
        logo_position=logo_position,
        logo_scale=round(logo_scale, 4),
        logo_margin=round(logo_margin, 4),
        subject_position=subject_position,
        negative_space=negative_space,
        focus_x=round(focus_x, 4),
        focus_y=round(focus_y, 4),
        rule_of_thirds=bool(thirds),
        visual_balance=round(balance, 4),
        dominant_colors=[c for c, _ in colors.most_common(4)],
        notes=notes,
    )


def _find_bands(density: list[float], threshold: float) -> list[tuple[int, int]]:
    bands: list[tuple[int, int]] = []
    start: int | None = None
    for i, v in enumerate(density):
        if v >= threshold and start is None:
            start = i
        elif v < threshold and start is not None:
            if i - start >= 2:
                bands.append((start, i - 1))
            start = None
    if start is not None and len(density) - start >= 2:
        bands.append((start, len(density) - 1))
    # Merge bands that are very close (same line)
    merged: list[tuple[int, int]] = []
    for band in bands:
        if merged and band[0] - merged[-1][1] <= 2:
            merged[-1] = (merged[-1][0], band[1])
        else:
            merged.append(band)
    return merged[:6]


def _detect_logo(
    sat_mask: list[list[int]], luma: list[list[float]], w: int, h: int
) -> tuple[str, float, float]:
    corners = {
        "top_left": (0, 0, w // 4, h // 4),
        "top_right": (3 * w // 4, 0, w, h // 4),
        "bottom_left": (0, 3 * h // 4, w // 4, h),
        "bottom_right": (3 * w // 4, 3 * h // 4, w, h),
    }
    best_name = "bottom_left"
    best_score = -1.0
    best_scale = 0.10
    best_margin = 0.04
    for name, (x0, y0, x1, y1) in corners.items():
        hits = 0
        area = max(1, (x1 - x0) * (y1 - y0))
        xs: list[int] = []
        ys: list[int] = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                if sat_mask[y][x] and 30 <= luma[y][x] <= 220:
                    hits += 1
                    xs.append(x)
                    ys.append(y)
        score = hits / area
        if score > best_score:
            best_score = score
            best_name = name
            if xs and ys:
                bw = (max(xs) - min(xs) + 1) / w
                bh = (max(ys) - min(ys) + 1) / h
                best_scale = max(0.06, min(0.22, max(bw, bh)))
                if "left" in name:
                    best_margin = max(0.02, min(0.08, min(xs) / w))
                else:
                    best_margin = max(0.02, min(0.08, (w - max(xs)) / w))
    if best_score < 0.02:
        return "bottom_left", 0.10, 0.04
    return best_name, best_scale, best_margin


def _detect_focus(
    luma: list[list[float]], text_position: str, w: int, h: int
) -> tuple[float, float, float]:
    # Edge energy map
    best = 0.0
    bx, by = 0.68, 0.45
    x_range = range(w // 2, w) if text_position == "left" else (
        range(0, w // 2) if text_position == "right" else range(w // 4, 3 * w // 4)
    )
    for y in range(1, h - 1, 2):
        for x in x_range:
            if x <= 0 or x >= w - 1:
                continue
            e = abs(luma[y][x] - luma[y][x - 1]) + abs(luma[y][x] - luma[y - 1][x])
            if e > best:
                best = e
                bx, by = x / w, y / h
    left_energy = sum(
        abs(luma[y][x] - luma[y][max(0, x - 1)])
        for y in range(0, h, 3)
        for x in range(0, w // 2, 3)
    )
    right_energy = sum(
        abs(luma[y][x] - luma[y][max(0, x - 1)])
        for y in range(0, h, 3)
        for x in range(w // 2, w, 3)
    )
    total = left_energy + right_energy + 1e-6
    balance = right_energy / total
    return bx, by, balance


def _outline_shadow_likelihood(
    text_mask: list[list[int]], luma: list[list[float]], w: int, h: int
) -> tuple[bool, bool]:
    edge_dark = 0
    edge_total = 0
    below_dark = 0
    for y in range(1, h - 2):
        for x in range(1, w - 2):
            if not text_mask[y][x]:
                continue
            if text_mask[y][x - 1] and text_mask[y][x + 1]:
                continue
            edge_total += 1
            if luma[y][x] - luma[y][max(0, x - 2)] > 40:
                edge_dark += 1
            if luma[y + 2][x] < luma[y][x] - 25:
                below_dark += 1
    if edge_total < 20:
        return True, True
    outline = (edge_dark / edge_total) >= 0.25
    shadow = (below_dark / edge_total) >= 0.18
    return outline, shadow
