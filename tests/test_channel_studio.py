"""Channel Studio pack load / save / reference tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.channels.models import Channel
from app.channels.studio.assets import install_named_asset, resolve_studio_asset
from app.channels.studio.models import ChannelStudioPack, StudioGeneral
from app.channels.studio.paths import (
    BRAND_KIT_FILE,
    BRANDING_DIR,
    GENERAL_FILE,
    GOALS_FILE,
    REFERENCE_KINDS,
    THUMBNAIL_SETTINGS_FILE,
    branding_dir,
    channel_studio_dir,
)
from app.channels.studio.service import ChannelStudioService
from app.channels.studio.sync import sync_studio_to_creative
from app.core.storage_paths import CREATIVE


class ChannelStudioServiceTests(unittest.TestCase):
    def test_ensure_save_load_and_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = ChannelStudioService(root)
            channel = Channel.create_default("Hollow Atlas")
            channel.description = "Cinematic mystery documentary"
            channel.outro_line = "Stay curious."
            channel.voice = {
                "provider": "kokoro",
                "voice_name": "Adam",
                "voice_id": "am_adam",
                "speed": 1.0,
            }

            pack = service.ensure("Hollow Atlas", channel=channel)
            self.assertIsInstance(pack, ChannelStudioPack)
            self.assertEqual(pack.general.name, "Hollow Atlas")
            self.assertEqual(pack.general.description, "Cinematic mystery documentary")
            self.assertEqual(pack.brand.outro, "Stay curious.")
            self.assertEqual(pack.voice.voice, "Adam")

            base = channel_studio_dir(root, "Hollow Atlas")
            self.assertTrue((base / GENERAL_FILE).is_file())
            self.assertTrue((base / BRAND_KIT_FILE).is_file())
            self.assertTrue((base / THUMBNAIL_SETTINGS_FILE).is_file())
            self.assertTrue((base / GOALS_FILE).is_file())
            for kind in REFERENCE_KINDS:
                self.assertTrue((base / "references" / kind).is_dir())

            pack.general.niche = "mystery"
            pack.general.tone_of_voice = "calm documentary"
            pack.thumbnail.max_words = 3
            pack.image.lighting = "moonlit"
            pack.goals.ctr_goal = 8.5
            service.save(pack, channel=channel)
            self.assertEqual(channel.description, "Cinematic mystery documentary")
            self.assertEqual(channel.voice.get("voice_name"), "Adam")

            loaded = service.load("Hollow Atlas")
            self.assertEqual(loaded.general.niche, "mystery")
            self.assertEqual(loaded.general.tone_of_voice, "calm documentary")
            self.assertEqual(loaded.thumbnail.max_words, 3)
            self.assertEqual(loaded.image.lighting, "moonlit")
            self.assertEqual(loaded.goals.ctr_goal, 8.5)

            sample = root / "ref.png"
            sample.write_bytes(b"png-bytes")
            dest = service.add_reference("Hollow Atlas", "thumbnails", sample)
            self.assertTrue(dest.is_file())
            self.assertEqual(service.reference_counts("Hollow Atlas")["thumbnails"], 1)
            self.assertEqual(len(service.list_references("Hollow Atlas", "thumbnails")), 1)

            service.delete_reference("Hollow Atlas", "thumbnails", dest)
            self.assertEqual(service.reference_counts("Hollow Atlas")["thumbnails"], 0)

    def test_sync_writes_creative_brand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = ChannelStudioService(root)
            pack = service.ensure("Mirror Drift")
            pack.general.name = "Mirror Drift"
            pack.brand.primary_color = "#1a1a2e"
            pack.brand.cta = "Drift deeper."
            pack.thumbnail.max_words = 4
            service.save(pack)
            sync_studio_to_creative(root, pack)
            # Creative keys may be normalized; check under either folder style.
            creative_root = root / CREATIVE
            self.assertTrue(creative_root.is_dir())
            brand_files = list(creative_root.rglob("brand_kit.json"))
            self.assertTrue(brand_files)

    def test_studio_general_roundtrip(self) -> None:
        general = StudioGeneral(
            name="Demo",
            niche="tech",
            audience="curious adults",
            language="en-US",
            tone_of_voice="warm",
            upload_frequency="2x/week",
            channel_type="education",
        )
        restored = StudioGeneral.from_dict(general.to_dict())
        self.assertEqual(restored.niche, "tech")
        self.assertEqual(restored.channel_type, "education")

    def test_load_basics_skips_heavy_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = ChannelStudioService(root)
            channel = Channel.create_default("Hollow Atlas")
            channel.description = "Basics only"
            channel.logo = "branding/logo.png"
            service.ensure("Hollow Atlas", channel=channel)

            pack = service.load_basics("Hollow Atlas", channel=channel)
            self.assertEqual(pack.general.name, "Hollow Atlas")
            self.assertEqual(pack.general.description, "Basics only")
            self.assertEqual(pack.brand.logo, "branding/logo.png")
            # Defaults — not hydrated until the tab opens.
            self.assertEqual(pack.thumbnail.max_words, 4)
            self.assertEqual(pack.goals.uploads_per_week, 1.0)

            thumb = service.load_section("Hollow Atlas", "thumbnail")
            self.assertEqual(thumb.max_words, 4)
            service.apply_section(pack, "thumbnail", thumb)
            pack.thumbnail.max_words = 2
            # Simulate partial edit + hydrate_missing before save.
            loaded = {"general", "brand", "thumbnail"}
            service.hydrate_missing(pack, loaded)
            self.assertEqual(pack.thumbnail.max_words, 2)
            self.assertTrue(pack.rules)

    def test_install_brand_asset_copies_locally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = ChannelStudioService(root)
            service.ensure("Hollow Atlas")
            source = root / "source_logo.png"
            source.write_bytes(b"fake-png")

            relative = service.install_brand_asset("Hollow Atlas", "logo", source)
            self.assertEqual(relative, "branding/logo.png")
            dest = branding_dir(root, "Hollow Atlas") / "logo.png"
            self.assertTrue(dest.is_file())
            self.assertEqual(dest.read_bytes(), b"fake-png")

            resolved = resolve_studio_asset(root, "Hollow Atlas", relative)
            self.assertEqual(resolved, dest.resolve())

            # Replace with webp — old png removed.
            source2 = root / "new.webp"
            source2.write_bytes(b"webp")
            relative2 = install_named_asset(
                root,
                "Hollow Atlas",
                asset_key="logo",
                source=source2,
                subdir=BRANDING_DIR,
            )
            self.assertEqual(relative2, "branding/logo.webp")
            self.assertFalse(dest.exists())
            self.assertTrue((branding_dir(root, "Hollow Atlas") / "logo.webp").is_file())

    def test_personality_and_training_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = ChannelStudioService(root)
            pack = service.ensure("Hollow Atlas")
            pack.general.name = "Hollow Atlas"
            pack.general.description = "Cinematic mystery"
            pack.brand.logo = "branding/logo.png"
            pack.personality = pack.personality.default_profile()
            pack.thumbnail.emotion = "mystery"
            pack.thumbnail.dominant_subject = "one"
            pack.image.lighting = "warm_cinematic"
            pack.image.mood = "mystery"
            pack.story.hook_type = "question"
            pack.voice.voice_style = "documentary"
            pack.voice.voice = "Adam"
            pack.music.personality = "mystery"
            service.save(pack)

            loaded = service.load_section("Hollow Atlas", "personality")
            self.assertEqual(loaded.traits["mystery"], 100)
            self.assertGreaterEqual(loaded.traits["epic"], 90)

            from app.channels.studio.training import evaluate_training

            progress = evaluate_training(service.load("Hollow Atlas"))
            self.assertGreaterEqual(progress.percent, 50)
            self.assertTrue(progress.completed["personality"])
            self.assertTrue(progress.completed["brand"])


if __name__ == "__main__":
    unittest.main()
