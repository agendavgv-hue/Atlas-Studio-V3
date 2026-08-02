"""Thumbnail Style DNA engine tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.channels.models import Channel
from app.channels.studio.service import ChannelStudioService
from app.creative.engine.style_profile_service import StyleProfileService
from app.thumbnail.style_dna.analyzer import ThumbnailStyleAnalyzer
from app.thumbnail.style_dna.layout import split_hook_lines, text_layout_from_dna
from app.thumbnail.style_dna.service import ThumbnailStyleDNAService
from app.thumbnail.text_overlay import render_thumbnail_text


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _ref_png(path: Path, *, stacked: bool = True) -> None:
    """Synthetic left-stacked yellow headline + right subject + bottom-left logo."""
    _ensure_app()
    image = QImage(320, 180, QImage.Format.Format_ARGB32)
    image.fill(QColor("#101820"))
    painter = QPainter(image)
    # Subject mass on the right
    painter.fillRect(190, 30, 110, 130, QColor("#8a6a28"))
    # Logo bottom-left
    painter.fillRect(12, 150, 28, 18, QColor("#c9a227"))
    # Stacked headline lines (bright)
    if stacked:
        painter.fillRect(16, 22, 90, 22, QColor("#fff2c8"))
        painter.fillRect(16, 50, 110, 24, QColor("#ffe08a"))
        painter.fillRect(16, 80, 100, 22, QColor("#fff2c8"))
    else:
        painter.fillRect(16, 28, 140, 36, QColor("#fff2c8"))
    painter.end()
    image.save(str(path), "PNG")


class StyleDNATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_app()

    def test_analyzer_learns_layout_from_all_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            refs = []
            for i in range(3):
                path = root / f"ref_{i}.png"
                _ref_png(path, stacked=True)
                refs.append(path)
            dna = ThumbnailStyleAnalyzer().analyze(refs)
            self.assertEqual(dna.reference_count, 3)
            self.assertEqual(dna.text_position, "left")
            self.assertEqual(dna.subject_position, "right")
            self.assertEqual(dna.negative_space, "left")
            self.assertGreaterEqual(dna.text_max_lines, 2)
            self.assertGreater(dna.text_coverage, 0.1)
            self.assertIn(dna.logo_position, {
                "bottom_left", "bottom_right", "top_left", "top_right"
            })
            self.assertTrue(dna.to_dict()["text_position"])

    def test_service_writes_thumbnail_style_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            studio.ensure("Night Orchard", channel=Channel.create_default("Night Orchard"))
            for i in range(2):
                path = root / f"up_{i}.png"
                _ref_png(path)
                studio.add_reference("Night Orchard", "thumbnails", path)

            dna = ThumbnailStyleDNAService(root).ensure("Night Orchard", force=True)
            path = ThumbnailStyleDNAService(root).profile_path("Night Orchard")
            self.assertTrue(path.is_file())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["text_position"], dna.text_position)
            self.assertIn("text_max_lines", payload)
            self.assertIn("headline_scale", payload)
            self.assertIn("logo_scale", payload)
            self.assertIn("line_break_mode", payload)
            self.assertIn("samples", payload)
            self.assertGreaterEqual(len(payload["samples"]), 2)

            # StyleProfileService bridges to legacy consumers.
            profile = StyleProfileService(root).ensure_thumbnail_profile(
                "Night Orchard", force=True
            )
            self.assertEqual(profile.reference_count, 2)
            self.assertEqual(profile.text_position, dna.text_position)

    def test_stacked_line_break_and_text_overlay(self) -> None:
        lines = split_hook_lines(
            "THE MARY CELESTE",
            max_words=4,
            max_lines=3,
            line_break_mode="stacked_words",
        )
        self.assertEqual(lines, ["THE", "MARY", "CELESTE"])

        folded = split_hook_lines(
            "THE MARY CELESTE MYSTERY",
            max_words=4,
            max_lines=3,
            line_break_mode="stacked_words",
        )
        self.assertEqual(folded, ["THE", "MARY", "CELESTE MYSTERY"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            refs = [root / "a.png"]
            _ref_png(refs[0], stacked=True)
            dna = ThumbnailStyleAnalyzer().analyze(refs)
            dna.line_break_mode = "stacked_words"
            dna.text_max_lines = 3
            dna.headline_scale = 1.8
            layout = text_layout_from_dna(dna)
            self.assertIsNotNone(layout)
            assert layout is not None
            base = QImage(640, 360, QImage.Format.Format_ARGB32)
            base.fill(QColor("#182028"))
            from PySide6.QtCore import QByteArray, QBuffer, QIODevice

            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            base.save(buf, "PNG")
            buf.close()
            out = render_thumbnail_text(
                bytes(ba),
                "THE MARY CELESTE",
                channel_name="Demo",
                layout=layout,
                max_words=3,
            )
            self.assertGreater(len(out), 100)


if __name__ == "__main__":
    unittest.main()
