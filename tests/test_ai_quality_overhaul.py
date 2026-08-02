"""Sprint 2 — AI Quality Overhaul regression tests."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.pipelines.context import ChannelDefaults
from app.pipelines.sheet_format import CANONICAL_SHEET_EXAMPLE, CANONICAL_SHEET_LAYOUT
from app.pipelines.sheet_prompts import extract_image_prompts
from app.pipelines.sheet_validation import validate_production_sheet
from app.prompts import defaults
from app.prompts.assembler import PromptAssembler
from app.thumbnail.text_overlay import render_thumbnail_text


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def test_script_instruction_is_documentary_length() -> None:
    text = defaults.SCRIPT_PIPELINE_INSTRUCTION.casefold()
    assert "4:00" in text or "4 minutes" in text or "600 words" in text
    assert "hook" in text


def test_sheet_layout_requires_director_fields() -> None:
    layout = CANONICAL_SHEET_LAYOUT
    for label in (
        "Scene Goal:",
        "Camera Direction:",
        "Composition:",
        "Lighting:",
        "Mood:",
        "Color Palette:",
        "Foreground:",
        "Midground:",
        "Background:",
        "Subject:",
        "Visual Focus:",
        "Prompt:",
        "Negative Prompt:",
        "Recommended Duration:",
    ):
        assert label in layout
    assert "Do not replace Prompt:" in layout
    assert "exactly 15" in layout.casefold() or "IMAGE 15" in layout


def test_canonical_example_validates() -> None:
    report = validate_production_sheet(CANONICAL_SHEET_EXAMPLE)
    assert report.ok, report.errors
    assert report.scene_count == 15
    assert len(extract_image_prompts(CANONICAL_SHEET_EXAMPLE)) == 15


def test_image_assembler_applies_house_style_and_negatives() -> None:
    from types import SimpleNamespace

    from app.projects.models import Project

    assembler = PromptAssembler()
    project = Project(
        name="Demo",
        folder_name="P001",
        channel_name="Hollow Atlas",
        idea="Atlantis",
    )
    ctx = SimpleNamespace(
        channel_name="Hollow Atlas",
        project_name="Demo",
        project=project,
        channel_defaults=ChannelDefaults(name="Hollow Atlas"),
    )

    request = assembler.image_prompt(ctx, "bronze statue in ruins, cinematic")  # type: ignore[arg-type]
    assert "photorealistic" in request.prompt.casefold()
    assert "hollow atlas" in request.prompt.casefold()
    assert "warm gold" in request.prompt.casefold() or "charcoal" in request.prompt.casefold()
    assert "watermark" in request.negative_prompt.casefold()
    assert "fantasy" in request.negative_prompt.casefold() or "cgi" in request.negative_prompt.casefold()


def test_thumbnail_text_overlay_renders_png() -> None:
    _ensure_app()
    # 1x1 is too small; make a simple solid image via QImage
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage

    image = QImage(1280, 720, QImage.Format.Format_ARGB32)
    image.fill(QColor("#222222"))
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    raw = bytes(ba)
    out = render_thumbnail_text(raw, "SECRET FOUND", channel_name="Hollow Atlas")
    assert out and out[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(out) > len(raw) // 2


def test_channel_json_styles_filled() -> None:
    root = Path(__file__).resolve().parents[1] / "channels"
    for name in ("Hollow Atlas", "Mirror Drift"):
        data = (root / name / "channel.json").read_text(encoding="utf-8")
        assert '"image_prompt": ""' not in data
        assert "house style" in data.casefold() or "cinematic" in data.casefold()
