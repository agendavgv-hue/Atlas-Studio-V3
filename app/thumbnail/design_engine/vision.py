"""Vision analysis of the AI illustration → SceneMap."""

from __future__ import annotations

from PySide6.QtGui import QColor, QImage

from app.thumbnail.design_engine.models import RectNorm, SceneMap

_W = 160
_H = 90


def analyze_illustration(image_png: bytes) -> SceneMap:
    """Heuristic scene map — no OCR, works offline for any channel."""
    image = QImage.fromData(image_png)
    if image.isNull():
        return SceneMap(notes=["empty illustration"])
    sample = image.scaled(_W, _H)
    w, h = sample.width(), sample.height()
    luma = [[0.0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            c = QColor(sample.pixel(x, y))
            luma[y][x] = 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()

    # Edge energy for subject
    energy = [[0.0] * w for _ in range(h)]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            energy[y][x] = abs(luma[y][x] - luma[y][x - 1]) + abs(
                luma[y][x] - luma[y - 1][x]
            )

    # Focus = peak energy
    best_e, fx, fy = -1.0, w // 2, h // 2
    for y in range(h):
        for x in range(w):
            if energy[y][x] > best_e:
                best_e = energy[y][x]
                fx, fy = x, y

    # Subject bbox: expand around high-energy cells
    thresh = best_e * 0.35 if best_e > 0 else 20
    xs: list[int] = []
    ys: list[int] = []
    for y in range(h):
        for x in range(w):
            if energy[y][x] >= thresh:
                xs.append(x)
                ys.append(y)
    if xs and ys:
        subject = RectNorm(
            x=max(0.0, (min(xs) - 2) / w),
            y=max(0.0, (min(ys) - 2) / h),
            w=min(1.0, (max(xs) - min(xs) + 5) / w),
            h=min(1.0, (max(ys) - min(ys) + 5) / h),
        )
    else:
        subject = RectNorm(x=0.45, y=0.2, w=0.5, h=0.7)

    # Horizon: row with strongest horizontal change in mid band
    horizon_y = 0.42
    best_row = 0.0
    for y in range(h // 5, 3 * h // 5):
        row = sum(abs(luma[y][x] - luma[y][x - 1]) for x in range(1, w))
        if row > best_row:
            best_row = row
            horizon_y = y / h

    sky_ratio = max(0.1, min(0.7, horizon_y))
    # Water heuristic: lower third cooler/darker average
    lower = [luma[y][x] for y in range(2 * h // 3, h) for x in range(w)]
    water_ratio = 0.25 if lower and (sum(lower) / len(lower)) < 90 else 0.0

    left_avg = sum(luma[y][x] for y in range(h) for x in range(w // 3)) / max(
        1, h * (w // 3)
    )
    right_avg = sum(
        luma[y][x] for y in range(h) for x in range(2 * w // 3, w)
    ) / max(1, h * (w - 2 * w // 3))
    dark_side = "left" if left_avg <= right_avg else "right"
    light_side = "right" if dark_side == "left" else "left"

    # Negative space = side with lower edge energy
    left_e = sum(energy[y][x] for y in range(h) for x in range(w // 3))
    right_e = sum(energy[y][x] for y in range(h) for x in range(2 * w // 3, w))
    negative_space = "left" if left_e <= right_e else "right"

    # Gaze: subject center vs frame center
    subject_cx = subject.x + subject.w / 2
    gaze = "left" if subject_cx > 0.55 else "right" if subject_cx < 0.45 else "center"

    # Face-ish: upper portion of subject with higher luma variance
    faces: list[RectNorm] = []
    if subject.h > 0.15:
        faces.append(
            RectNorm(
                x=subject.x + subject.w * 0.2,
                y=subject.y,
                w=subject.w * 0.6,
                h=subject.h * 0.35,
            )
        )

    objects = [
        RectNorm(
            x=subject.x,
            y=subject.y + subject.h * 0.45,
            w=subject.w,
            h=subject.h * 0.5,
        )
    ]

    return SceneMap(
        subject=subject,
        focus_x=fx / w,
        focus_y=fy / h,
        horizon_y=horizon_y,
        sky_ratio=sky_ratio,
        water_ratio=water_ratio,
        dark_side=dark_side,
        light_side=light_side,
        negative_space=negative_space,
        gaze_direction=gaze,
        face_regions=faces,
        object_regions=objects,
        notes=[
            f"subject={subject.w:.2f}x{subject.h:.2f}",
            f"neg={negative_space}",
            f"focus=({fx / w:.2f},{fy / h:.2f})",
        ],
    )
