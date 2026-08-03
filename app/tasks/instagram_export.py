"""Thin Instagram image + export helpers for one-click production.

Instagram Image: professional square social still with channel branding.
Export: verify the YouTube final video artifact from the Movie step.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from app.artifacts import ArtifactKind, ArtifactResolver
from app.pipelines.image_naming import resolve_images_dir
from app.pipelines.results import PipelineResult
from app.thumbnail.naming import thumbnail_path, thumbnail_title_path


INSTA_FOLDER = "insta"
INSTA_BASENAME = "instagram.png"


def resolve_insta_dir(project_dir: Path) -> Path:
    folder = project_dir.expanduser().resolve() / INSTA_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def instagram_image_path(project_dir: Path) -> Path:
    return resolve_insta_dir(project_dir) / INSTA_BASENAME


def _source_still(project_dir: Path) -> Path | None:
    # Prefer a clean image (no thumbnail headline) for Instagram redesign.
    resolver = ArtifactResolver(project_dir)
    images = resolver.find_all(ArtifactKind.IMAGES)
    if images:
        return sorted(images)[0]
    images_dir = resolve_images_dir(project_dir)
    if images_dir.is_dir():
        candidates = sorted(
            p
            for p in images_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
        if candidates:
            return candidates[0]
    thumb = thumbnail_path(project_dir)
    if thumb.is_file():
        return thumb
    return None


def _channel_name_from_project(project_dir: Path) -> str:
    # project_dir is typically .../<Channel>/<ProjectFolder>
    try:
        return project_dir.expanduser().resolve().parent.name
    except OSError:
        return ""


def _hook_text(project_dir: Path) -> str:
    path = thumbnail_title_path(project_dir)
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def create_instagram_image(project_dir: Path) -> PipelineResult:
    """Create a branded 1080×1080 Instagram still (not a raw thumbnail crop)."""
    started = time.perf_counter()
    source = _source_still(project_dir)
    if source is None:
        return PipelineResult.failed(
            "No images available for Instagram.",
            errors=["Generate Images or Thumbnail before Instagram Image."],
            execution_time_ms=(time.perf_counter() - started) * 1000.0,
        )

    dest = instagram_image_path(project_dir)
    channel = _channel_name_from_project(project_dir)
    hook = _hook_text(project_dir)
    try:
        written = _compose_instagram_square(source, dest, channel_name=channel, hook=hook)
        if not written:
            shutil.copy2(source, dest)
    except OSError as exc:
        return PipelineResult.failed(
            f"Could not write Instagram image: {exc}",
            errors=[str(exc)],
            execution_time_ms=(time.perf_counter() - started) * 1000.0,
        )

    rel = f"{INSTA_FOLDER}/{INSTA_BASENAME}"
    return PipelineResult.success(
        "Instagram image ready",
        artifacts=[rel],
        execution_time_ms=(time.perf_counter() - started) * 1000.0,
    )


def _compose_instagram_square(
    source: Path,
    dest: Path,
    *,
    channel_name: str,
    hook: str,
) -> bool:
    try:
        from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRect, Qt
        from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen
    except ImportError:
        return False

    image = QImage(str(source))
    if image.isNull():
        return False

    side = 1080
    canvas = QImage(side, side, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#0B0B0C"))

    # Cover-crop source into square.
    src_side = min(image.width(), image.height())
    x0 = (image.width() - src_side) // 2
    y0 = (image.height() - src_side) // 2
    cropped = image.copy(x0, y0, src_side, src_side).scaled(
        side,
        side,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawImage(0, 0, cropped)

    mirror = "mirror" in channel_name.casefold()
    accent = QColor("#3DB9FF") if mirror else QColor("#D4AF37")
    ink = QColor("#F5FBFF") if mirror else QColor("#FFF6D8")
    bar = QColor(6, 18, 32, 210) if mirror else QColor(12, 8, 2, 210)

    # Bottom branding band.
    band_h = 168
    painter.fillRect(0, side - band_h, side, band_h, bar)
    painter.fillRect(0, side - band_h, side, 4, accent)

    brand = (channel_name or "ATLAS STUDIO").strip().upper() or "ATLAS STUDIO"
    font_brand = QFont("Segoe UI")
    font_brand.setBold(True)
    font_brand.setPointSize(22)
    painter.setFont(font_brand)
    painter.setPen(QPen(accent))
    painter.drawText(QRect(36, side - band_h + 18, side - 72, 36), Qt.AlignmentFlag.AlignLeft, brand)

    line = " ".join((hook or "NEW DROP").strip().upper().split()) or "NEW DROP"
    font_hook = QFont("Segoe UI Black")
    if not font_hook.exactMatch():
        font_hook = QFont("Impact")
    font_hook.setBold(True)
    font_hook.setPointSize(34)
    metrics = QFontMetrics(font_hook)
    while font_hook.pointSize() > 18 and metrics.horizontalAdvance(line) > side - 72:
        font_hook.setPointSize(font_hook.pointSize() - 2)
        metrics = QFontMetrics(font_hook)
    painter.setFont(font_hook)
    painter.setPen(QPen(ink))
    painter.drawText(
        QRect(36, side - band_h + 58, side - 72, 78),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        line,
    )

    painter.end()

    dest.parent.mkdir(parents=True, exist_ok=True)
    ba = QByteArray()
    buffer = QBuffer(ba)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    ok = canvas.save(buffer, "PNG")
    buffer.close()
    if not ok:
        return False
    dest.write_bytes(bytes(ba))
    return True


def verify_youtube_export(project_dir: Path) -> PipelineResult:
    """Confirm Movie export artifact exists (no re-render)."""
    started = time.perf_counter()
    from app.render.naming import FINAL_BASENAME, YOUTUBE_FOLDER

    path = project_dir.expanduser().resolve() / YOUTUBE_FOLDER / FINAL_BASENAME
    if not path.is_file() or path.stat().st_size <= 0:
        return PipelineResult.failed(
            "YouTube export not found. Generate Movie before Export.",
            errors=[f"Missing export: {path}"],
            execution_time_ms=(time.perf_counter() - started) * 1000.0,
        )
    rel = f"{path.parent.name}/{path.name}"
    return PipelineResult.success(
        "Export verified",
        artifacts=[rel],
        execution_time_ms=(time.perf_counter() - started) * 1000.0,
    )
