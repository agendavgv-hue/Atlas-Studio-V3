"""AI Channel Creator — NEW channels only; Hollow Atlas / Mirror Drift locked."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.channels.ai_channel_creator import AIChannelCreator
from app.channels.channel_profile_store import ChannelProfilePackStore
from app.channels.channel_service import ChannelService
from app.channels.generated_profile import GeneratedChannelProfile
from app.channels.reference_channels import (
    REFERENCE_CHANNEL_NAMES,
    assert_not_reference_channel,
    is_reference_channel,
)
from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.prompts.style_engine import (
    CHANNEL_PROFILES,
    HOLLOW_ATLAS,
    MIRROR_DRIFT,
    build_modular_image_prompt,
    resolve_profile,
)
from app.thumbnail.dna_loader import ChannelDNALoader, _PACKAGED_DNA_PATH
from app.thumbnail.style_loader import ChannelStyleLoader, _PACKAGED_STYLE_PATH


def _service(tmp: Path) -> tuple[ChannelService, Path, Path]:
    data_root = tmp / "atlas_data"
    project_root = tmp / "youtube"
    project_root.mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    storage = Storage(config)
    storage.ensure_structure()
    return ChannelService(storage, config), data_root, project_root


class ReferenceChannelLockTests(unittest.TestCase):
    def test_reference_names_are_locked(self) -> None:
        self.assertTrue(is_reference_channel("Hollow Atlas"))
        self.assertTrue(is_reference_channel("mirror drift"))
        self.assertFalse(is_reference_channel("Night Orchard"))
        with self.assertRaises(ValueError):
            assert_not_reference_channel("Hollow Atlas", action="create")

    def test_ai_creator_refuses_reference_names(self) -> None:
        creator = AIChannelCreator(text_provider=None)
        for name in REFERENCE_CHANNEL_NAMES:
            with self.assertRaises(ValueError):
                creator.generate(name=name, concept="should fail")

    def test_profile_store_refuses_reference_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ChannelProfilePackStore(Path(tmp) / "data")
            with self.assertRaises(ValueError):
                store.upsert_dna("Hollow Atlas", {"signature": "hacked"})
            with self.assertRaises(ValueError):
                store.upsert_style("Mirror Drift", {"colors": "hacked"})


class BackwardsCompatibilityTests(unittest.TestCase):
    def test_style_engine_profiles_unchanged(self) -> None:
        self.assertIs(resolve_profile("Hollow Atlas"), HOLLOW_ATLAS)
        self.assertIs(resolve_profile("Mirror Drift"), MIRROR_DRIFT)
        self.assertEqual(set(CHANNEL_PROFILES), {"Hollow Atlas", "Mirror Drift"})

    def test_hollow_atlas_prompt_identity_preserved(self) -> None:
        prompt, neg = build_modular_image_prompt(
            scene="ancient doorway in stone ruins",
            channel_name="Hollow Atlas",
        )
        text = prompt.casefold()
        self.assertTrue("warm gold" in text or "charcoal" in text or "museum" in text)
        self.assertTrue("god rays" in text or "volumetric" in text or "bronze" in text)
        self.assertNotIn("electric blue chrome", text)

    def test_mirror_drift_prompt_identity_preserved(self) -> None:
        prompt, neg = build_modular_image_prompt(
            scene="precision robot arm in a clean lab",
            channel_name="Mirror Drift",
        )
        text = prompt.casefold()
        self.assertTrue("electric blue" in text or "graphite" in text or "chrome" in text)
        self.assertNotIn("warm gold museum", text)
        self.assertTrue(
            "ancient ruins" in neg.casefold()
            or "warm gold" in neg.casefold()
            or "museum dust" in neg.casefold()
        )

    def test_packaged_dna_survives_assets_overlay(self) -> None:
        packaged = json.loads(_PACKAGED_DNA_PATH.read_text(encoding="utf-8"))
        ha_sig = packaged["Hollow Atlas"]["signature"]
        md_sig = packaged["Mirror Drift"]["signature"]

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data"
            store = ChannelProfilePackStore(data_root)
            store.upsert_dna(
                "Night Orchard",
                {"display_name": "Night Orchard", "signature": "orchard signature"},
            )
            # Assets file must not contain reference keys.
            assets = json.loads(store.dna_path.read_text(encoding="utf-8"))
            self.assertNotIn("Hollow Atlas", assets)
            self.assertNotIn("Mirror Drift", assets)
            self.assertIn("Night Orchard", assets)

            loader = ChannelDNALoader(data_root=data_root)
            packs = loader.load_all()
            self.assertEqual(packs["Hollow Atlas"].signature, ha_sig)
            self.assertEqual(packs["Mirror Drift"].signature, md_sig)
            self.assertEqual(packs["Night Orchard"].signature, "orchard signature")

    def test_packaged_style_survives_assets_overlay(self) -> None:
        packaged = json.loads(_PACKAGED_STYLE_PATH.read_text(encoding="utf-8"))
        ha_colors = packaged["Hollow Atlas"]["colors"]
        md_colors = packaged["Mirror Drift"]["colors"]

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data"
            store = ChannelProfilePackStore(data_root)
            store.upsert_style(
                "Night Orchard",
                {
                    "display_name": "Night Orchard",
                    "colors": "moonlit orchard greens",
                    "lighting": "soft moonlight",
                },
            )
            assets = json.loads(store.style_path.read_text(encoding="utf-8"))
            self.assertNotIn("Hollow Atlas", assets)
            self.assertIn("Night Orchard", assets)

            loader = ChannelStyleLoader(data_root=data_root)
            styles = loader.load_all()
            self.assertEqual(styles["Hollow Atlas"].colors, ha_colors)
            self.assertEqual(styles["Mirror Drift"].colors, md_colors)
            self.assertEqual(styles["Night Orchard"].colors, "moonlit orchard greens")


class NewChannelFromAICreatorTests(unittest.TestCase):
    def test_create_channel_from_profile_writes_own_dna(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, data_root, project_root = _service(Path(tmp))
            creator = AIChannelCreator(text_provider=None)
            profile = creator.generate(
                name="Night Orchard",
                concept="Quiet nocturnal nature stories under moonlight",
                tone="calm, lunar, intimate",
            )
            channel = service.create_channel_from_profile(profile)

            self.assertEqual(channel.name, "Night Orchard")
            self.assertTrue((project_root / "Night Orchard").is_dir())
            self.assertIn("Night Orchard", channel.image_prompt)
            self.assertTrue(channel.outro_line)
            self.assertNotIn("full episode", channel.outro_line.casefold())

            dna_path = data_root / "Assets" / "channel_dna.json"
            style_path = data_root / "Assets" / "channel_style.json"
            self.assertTrue(dna_path.is_file())
            self.assertTrue(style_path.is_file())
            dna = json.loads(dna_path.read_text(encoding="utf-8"))
            style = json.loads(style_path.read_text(encoding="utf-8"))
            self.assertIn("Night Orchard", dna)
            self.assertIn("Night Orchard", style)
            self.assertNotIn("Hollow Atlas", dna)
            self.assertNotIn("Mirror Drift", dna)

            loaded = ChannelDNALoader(data_root=data_root).get_dna("Night Orchard")
            self.assertEqual(loaded.display_name, "Night Orchard")
            self.assertTrue(loaded.signature)

            # New channel prompts use channel.json override (not HA/MD style engine).
            prompt, _ = build_modular_image_prompt(
                scene="moonlit orchard path",
                channel_name="Night Orchard",
                channel_style_override=channel.image_prompt,
            )
            self.assertIn("orchard", prompt.casefold())

    def test_cannot_ai_create_existing_or_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, project_root = _service(Path(tmp))
            (project_root / "Hollow Atlas").mkdir()
            service.create_channel("Hollow Atlas")

            ha_profile = GeneratedChannelProfile(
                name="Hollow Atlas",
                description="hack",
                image_prompt="hacked",
            )
            with self.assertRaises(ValueError):
                service.create_channel_from_profile(ha_profile)

            # Existing non-reference also blocked (wizard is create-only).
            service.create_channel("Already There")
            dup = GeneratedChannelProfile(
                name="Already There",
                description="x",
                image_prompt="x",
            )
            with self.assertRaises(ValueError):
                service.create_channel_from_profile(dup)

    def test_plain_create_channel_still_works_for_hollow_atlas(self) -> None:
        """Scenario 1: New Hollow Atlas project path — channel config untouched by AI."""
        with tempfile.TemporaryDirectory() as tmp:
            service, data_root, project_root = _service(Path(tmp))
            channel = service.create_channel("Hollow Atlas")
            self.assertEqual(channel.folder_name, "Hollow Atlas")
            self.assertTrue((project_root / "Hollow Atlas").is_dir())
            # AI creator must not have written Assets packs for HA.
            dna_path = data_root / "Assets" / "channel_dna.json"
            if dna_path.is_file():
                payload = json.loads(dna_path.read_text(encoding="utf-8"))
                self.assertNotIn("Hollow Atlas", payload)

            # Style engine identity still resolves.
            self.assertIs(resolve_profile("Hollow Atlas"), HOLLOW_ATLAS)

    def test_plain_create_channel_still_works_for_mirror_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, project_root = _service(Path(tmp))
            channel = service.create_channel("Mirror Drift")
            self.assertEqual(channel.folder_name, "Mirror Drift")
            self.assertTrue((project_root / "Mirror Drift").is_dir())
            self.assertIs(resolve_profile("Mirror Drift"), MIRROR_DRIFT)


if __name__ == "__main__":
    unittest.main()
