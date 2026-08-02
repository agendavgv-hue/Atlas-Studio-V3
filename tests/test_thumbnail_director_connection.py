"""Creative Director ↔ Thumbnail Generator connection tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPainter

from app.channels.models import Channel
from app.channels.studio.service import ChannelStudioService
from app.creative.engine import CreativeDirectorEngine
from app.creative.engine.style_profile_service import StyleProfileService
from app.thumbnail.brand_overlay import apply_brand_overlays
from app.thumbnail.director_prompt import build_director_led_thumbnail_plans
from app.thumbnail.intelligence.branding import LogoPlacement


def _write_png(path: Path, *, color: str = "#203040") -> None:
    image = QImage(128, 72, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    painter = QPainter(image)
    painter.fillRect(80, 10, 40, 50, QColor("#d4a017"))
    painter.end()
    image.save(str(path), "PNG")


class ThumbnailDirectorConnectionTests(unittest.TestCase):
    def test_style_profile_and_director_led_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            channel = Channel.create_default("Night Orchard")
            channel.description = "Nocturnal nature mystery"
            pack = studio.ensure("Night Orchard", channel=channel)
            pack.brand.primary_color = "#102018"
            pack.brand.secondary_color = "#0a0a0a"
            pack.brand.logo = "branding/logo.png"
            pack.thumbnail.emotion = "mystery"
            pack.thumbnail.max_words = 3
            pack.image.lighting = "moonlight"
            studio.save(pack)

            logo = root / "logo.png"
            _write_png(logo, color="#ffffff")
            studio.install_brand_asset("Night Orchard", "logo", logo)

            ref = root / "thumb_ref.png"
            _write_png(ref, color="#101820")
            studio.add_reference("Night Orchard", "thumbnails", ref)

            profiles = StyleProfileService(root)
            thumb_profile = profiles.ensure_thumbnail_profile("Night Orchard", force=True)
            self.assertGreaterEqual(thumb_profile.reference_count, 1)
            self.assertTrue(
                (root / "Channels" / "Night Orchard" / "thumbnail_style_profile.json").is_file()
                or profiles.thumbnail_profile_path("Night Orchard").is_file()
            )

            engine = CreativeDirectorEngine(root)
            brief = engine.build_brief("Night Orchard")
            plans = build_director_led_thumbnail_plans(
                brief,
                hero_subject="ancient stone gateway",
                hook="LOST GATE",
                thumbnail_profile=thumb_profile,
            )
            self.assertEqual(len(plans), 4)
            primary = plans[0].prompt
            self.assertIn("Night Orchard", primary)
            self.assertIn("REFERENCE STYLE", primary)
            self.assertIn("Do NOT paint any text", primary)
            self.assertIn("ancient stone gateway", primary.casefold())
            self.assertNotIn("Hollow Atlas", primary)

            # Logo overlay must paste real brand asset, not invent one.
            base = root / "base.png"
            _write_png(base, color="#222222")
            logo_resolved = studio.resolve_asset("Night Orchard", "branding/logo.png")
            self.assertIsNotNone(logo_resolved)
            out = apply_brand_overlays(
                base.read_bytes(),
                logo_path=logo_resolved,
                placement=LogoPlacement(
                    position="bottom_left",
                    size=0.2,
                    opacity=1.0,
                    margin_px=8,
                    auto_scaled=False,
                ),
            )
            self.assertGreater(len(out), 100)

            frame = root / "frame.png"
            _write_png(frame, color="#00000000")
            frame_rel = studio.install_brand_asset(
                "Night Orchard", "thumbnail_frame", frame
            )
            pack = studio.load_basics("Night Orchard")
            pack.brand.thumbnail_frame = frame_rel
            studio.save(pack)
            frame_resolved = studio.resolve_asset("Night Orchard", frame_rel)
            framed = apply_brand_overlays(
                base.read_bytes(),
                logo_path=logo_resolved,
                frame_path=frame_resolved,
                placement=LogoPlacement(
                    position="bottom_right",
                    size=0.15,
                    opacity=1.0,
                    margin_px=8,
                    auto_scaled=False,
                ),
            )
            self.assertGreater(len(framed), 100)

            report = engine.write_report(
                root / "proj",
                brief,
                domain="thumbnail",
                master_prompt_text=primary,
                thumbnail_profile_loaded=True,
                image_profile_loaded=False,
            )
            payload = report.read_text(encoding="utf-8")
            self.assertIn("Brand Kit Loaded", payload)
            self.assertIn("YES", payload)
            self.assertIn("Thumbnail Style Profile Loaded", payload)


if __name__ == "__main__":
    unittest.main()
