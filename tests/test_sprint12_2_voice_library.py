"""Sprint 12.2 — Voice Library, metadata, and channel preferences."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.channels.voice_preferences import (
    ChannelVoicePreferences,
    resolve_channel_voice_preferences,
)
from app.core.app_config import AppConfig
from app.core.voice_settings import VoiceSettings
from app.pipelines.context import ChannelDefaults, PipelineContext
from app.pipelines.engine import ProductionEngine
from app.projects.models import Project
from app.projects.project_service import ProjectService
from app.providers.voice_base import VoiceInfo
from app.providers.voice_metadata import (
    PREFERRED_VOICE_MISSING_WARNING,
    display_name_from_id,
    resolve_available_voice,
    select_closest_voice,
)


class VoiceMetadataTests(unittest.TestCase):
    def test_display_name_from_id(self) -> None:
        self.assertEqual(display_name_from_id("af_heart"), "Heart")
        self.assertEqual(display_name_from_id("am_michael"), "Michael")

    def test_select_closest_voice_prefers_gender_and_styles(self) -> None:
        voices = [
            VoiceInfo("af_bella", "Bella", "en-US", gender="Female", style_tags=("Warm",)),
            VoiceInfo(
                "am_michael",
                "Michael",
                "en-US",
                gender="Male",
                style_tags=("Deep", "Calm", "Documentary", "Authoritative"),
            ),
            VoiceInfo(
                "am_eric",
                "Eric",
                "en-US",
                gender="Male",
                style_tags=("Energetic", "Modern", "Confident"),
            ),
        ]
        hollow = select_closest_voice(
            voices,
            gender="Male",
            style_tags=["Deep", "Calm", "Documentary", "Authoritative", "Cinematic"],
        )
        assert hollow is not None
        self.assertEqual(hollow.voice_id, "am_michael")

        mirror = select_closest_voice(
            voices,
            gender="Male",
            style_tags=["Energetic", "Modern", "Confident", "Technology", "Engaging"],
        )
        assert mirror is not None
        self.assertEqual(mirror.voice_id, "am_eric")

    def test_resolve_available_voice_keeps_preferred(self) -> None:
        voices = [
            VoiceInfo("af_heart", "Heart", "en-US", gender="Female"),
            VoiceInfo("am_adam", "Adam", "en-US", gender="Male"),
        ]
        resolved, warning = resolve_available_voice(
            voices, preferred_voice_id="af_heart"
        )
        assert resolved is not None
        self.assertEqual(resolved.voice_id, "af_heart")
        self.assertEqual(warning, "")

    def test_resolve_available_voice_falls_back_with_warning(self) -> None:
        voices = [
            VoiceInfo(
                "am_michael",
                "Michael",
                "en-US",
                gender="Male",
                style_tags=("Deep", "Calm", "Documentary"),
            ),
            VoiceInfo("af_heart", "Heart", "en-US", gender="Female", style_tags=("Warm",)),
        ]
        resolved, warning = resolve_available_voice(
            voices,
            preferred_voice_id="am_missing_voice",
            gender="Male",
            style_tags=["Deep", "Calm", "Documentary"],
            language="en-US",
        )
        assert resolved is not None
        self.assertEqual(resolved.voice_id, "am_michael")
        self.assertEqual(warning, PREFERRED_VOICE_MISSING_WARNING)


class ChannelVoicePreferenceTests(unittest.TestCase):
    def test_hollow_atlas_defaults(self) -> None:
        prefs = resolve_channel_voice_preferences("Hollow Atlas", {})
        self.assertEqual(prefs.gender, "Male")
        self.assertIn("Documentary", prefs.style_tags)
        self.assertEqual(prefs.provider, "kokoro")

    def test_mirror_drift_defaults(self) -> None:
        prefs = resolve_channel_voice_preferences("Mirror Drift", {})
        self.assertEqual(prefs.gender, "Male")
        self.assertIn("Technology", prefs.style_tags)

    def test_auto_bind_closest_voice(self) -> None:
        voices = [
            VoiceInfo(
                "am_michael",
                "Michael",
                "en-US",
                gender="Male",
                style_tags=("Deep", "Calm", "Documentary"),
            )
        ]
        prefs = resolve_channel_voice_preferences(
            "Hollow Atlas", {}, voices=voices
        )
        self.assertEqual(prefs.voice_id, "am_michael")
        self.assertEqual(prefs.voice_name, "Michael")

    def test_apply_to_settings(self) -> None:
        prefs = ChannelVoicePreferences(
            voice_id="am_adam",
            voice_name="Adam",
            speed=1.1,
            language="en-GB",
        )
        merged = prefs.apply_to_settings(VoiceSettings(voice_id="af_heart", speed=1.0))
        self.assertEqual(merged.voice_id, "am_adam")
        self.assertEqual(merged.voice_name, "Adam")
        self.assertEqual(merged.speed, 1.1)
        self.assertEqual(merged.language, "en-GB")


class EngineChannelVoiceMergeTests(unittest.TestCase):
    def test_resolve_voice_settings_uses_channel_prefs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(data_root=root)
            config.voice = VoiceSettings(voice_id="af_heart", voice_name="Heart", speed=1.0)
            projects = ProjectService(config)
            engine = ProductionEngine(projects, config)
            project = Project(
                name="Demo",
                folder_name="001_Demo",
                channel_name="Hollow Atlas",
            )
            context = PipelineContext(
                project=project,
                project_dir=root / "001_Demo",
                channel_defaults=ChannelDefaults(
                    name="Hollow Atlas",
                    voice={
                        "provider": "kokoro",
                        "voice_id": "am_michael",
                        "voice_name": "Michael",
                        "speed": 0.95,
                        "language": "en-US",
                    },
                ),
            )
            settings = engine.resolve_voice_settings_for(context)
            self.assertEqual(settings.voice_id, "am_michael")
            self.assertEqual(settings.voice_name, "Michael")
            self.assertEqual(settings.speed, 0.95)


class ChannelStoreVoiceDefaultsTests(unittest.TestCase):
    def test_ensure_default_applies_profile(self) -> None:
        from app.channels.channel_paths import ChannelPaths
        from app.channels.channel_store import ChannelStore
        from app.core.storage import Storage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "library"
            library.mkdir()
            (library / "Hollow Atlas").mkdir()
            config = AppConfig(data_root=root / "data")
            storage = Storage(config)
            storage.ensure_structure()
            paths = ChannelPaths(storage, library)
            store = ChannelStore(paths)
            channel = store.ensure_default("Hollow Atlas")
            self.assertEqual(channel.voice.get("gender"), "Male")
            self.assertIn("Documentary", channel.voice.get("style_tags", []))


if __name__ == "__main__":
    unittest.main()
