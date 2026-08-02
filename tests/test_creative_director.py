"""Creative Director Framework foundation tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.channels.models import Channel
from app.core.storage_paths import CREATIVE, StoragePaths
from app.creative import (
    CreativeDirector,
    CreativeDirectorService,
    CreativeRule,
    ReferenceLibrary,
)
from app.creative.paths import REFERENCE_KINDS


class CreativeDirectorServiceTests(unittest.TestCase):
    def test_create_load_brand_style_rules_and_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = CreativeDirectorService(root)
            channel = Channel.create_default("Night Orchard")
            channel.description = "Quiet nocturnal nature"
            channel.image_prompt = "moonlit orchard mist"
            channel.outro_line = "Stay with the orchard."
            channel.voice = {"provider": "kokoro", "voice_name": "Adam", "speed": 1.05}

            director = service.create("Night Orchard", source=channel)
            self.assertIsInstance(director, CreativeDirector)
            self.assertEqual(director.channel_key, "night_orchard")
            self.assertTrue(
                (root / CREATIVE / "night_orchard" / "director.json").is_file()
            )
            self.assertTrue(
                (root / CREATIVE / "night_orchard" / "brand_kit.json").is_file()
            )
            self.assertTrue(
                (root / CREATIVE / "night_orchard" / "style_library.json").is_file()
            )

            loaded = service.load("Night Orchard")
            self.assertEqual(loaded.voice.provider, "kokoro")
            self.assertGreaterEqual(len(service.get_rules("Night Orchard")), 1)
            self.assertTrue(
                any(r.id == "keep_channel_identity" for r in service.get_rules("Night Orchard"))
            )

            brand = service.get_brand("Night Orchard")
            self.assertEqual(brand.outro, "Stay with the orchard.")
            style = service.get_style("Night Orchard")
            self.assertIn("orchard", style.color_palette.casefold())

            thumb = service.get_thumbnail_style("Night Orchard")
            self.assertEqual(thumb.max_words, 4)
            self.assertEqual(service.get_story_style("Night Orchard").endings, "Stay with the orchard.")

            refs = service.references("Night Orchard")
            refs.ensure_structure()
            for kind in REFERENCE_KINDS:
                self.assertTrue(refs.path_for(kind).is_dir())

            sample = root / "logo.png"
            sample.write_bytes(b"png")
            dest = refs.add_file("logo", sample)
            self.assertTrue(dest.is_file())
            self.assertEqual(refs.counts()["logo"], 1)

            tips = service.generate_recommendations("Night Orchard")
            self.assertTrue(tips)
            issues = service.validate("Night Orchard")
            # Missing brand colors is expected on fresh seed without brain colors.
            self.assertIsInstance(issues, list)

    def test_update_and_custom_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CreativeDirectorService(Path(tmp))
            service.create("Demo Channel")
            rules = list(service.get_rules("Demo Channel"))
            rules.append(
                CreativeRule(
                    id="no_text_in_image",
                    title="No baked-in text",
                    description="Image model must not paint headlines.",
                    category="thumbnail",
                    priority=95,
                )
            )
            service.update("Demo Channel", rules=rules)
            ids = {r.id for r in service.get_rules("Demo Channel")}
            self.assertIn("no_text_in_image", ids)

    def test_storage_paths_include_creative(self) -> None:
        paths = StoragePaths(Path("D:/AtlasData"))
        self.assertEqual(paths.creative.name, CREATIVE)

    def test_reference_library_rejects_unknown_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lib = ReferenceLibrary(Path(tmp), "Demo")
            with self.assertRaises(ValueError):
                lib.path_for("not_a_real_kind")


if __name__ == "__main__":
    unittest.main()
