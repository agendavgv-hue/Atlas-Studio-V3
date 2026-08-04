"""Channel language — multilingual support helpers and wiring."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.channels.language import (
    content_language_instruction,
    is_english,
    language_label,
    language_locale,
    normalize_language,
    seo_language_instruction,
    voice_matches_language,
)
from app.channels.production_profile import ChannelProductionProfile
from app.channels.studio.models import StudioGeneral
from app.pipelines.context import ChannelDefaults
from app.pipelines.scene_prompt_english import ensure_english_scene_prompt
from app.providers.voice_base import VoiceInfo


class NormalizeLanguageTests(unittest.TestCase):
    def test_default_english(self) -> None:
        self.assertEqual(normalize_language(None), "en")
        self.assertEqual(normalize_language(""), "en")

    def test_legacy_locales(self) -> None:
        self.assertEqual(normalize_language("en-US"), "en")
        self.assertEqual(normalize_language("nl-NL"), "nl")
        self.assertEqual(normalize_language("de-DE"), "de")

    def test_labels_and_aliases(self) -> None:
        self.assertEqual(normalize_language("Dutch"), "nl")
        self.assertEqual(normalize_language("Nederlands"), "nl")
        self.assertEqual(normalize_language("German"), "de")


class LanguageHelpersTests(unittest.TestCase):
    def test_labels_and_locales(self) -> None:
        self.assertEqual(language_label("nl"), "Dutch")
        self.assertEqual(language_locale("nl"), "nl-NL")
        self.assertTrue(is_english("en-US"))
        self.assertFalse(is_english("nl"))

    def test_prompt_instructions(self) -> None:
        en = content_language_instruction("en")
        self.assertIn("English", en)
        self.assertIn("OUTPUT LANGUAGE", en)
        nl = content_language_instruction("nl")
        self.assertIn("Dutch", nl)
        seo = seo_language_instruction("nl")
        self.assertIn("Dutch", seo)
        self.assertIn("title", seo.casefold())

    def test_voice_matches_language(self) -> None:
        self.assertTrue(voice_matches_language("en-US", "en"))
        self.assertTrue(voice_matches_language("en-GB", "en"))
        self.assertTrue(voice_matches_language("nl-NL", "nl"))
        self.assertTrue(voice_matches_language("nl", "nl"))
        self.assertFalse(voice_matches_language("en-US", "nl"))
        self.assertFalse(voice_matches_language("", "nl"))
        self.assertTrue(voice_matches_language("", "en"))


class SnapshotLanguageTests(unittest.TestCase):
    def test_profile_defaults_english(self) -> None:
        profile = ChannelProductionProfile.from_dict({})
        self.assertEqual(profile.language, "en")
        mapping = profile.to_channel_defaults_mapping()
        self.assertEqual(mapping["language"], "en")
        self.assertEqual(mapping["subtitles"]["language"], "en")

    def test_legacy_snapshot_without_language(self) -> None:
        defaults = ChannelDefaults.from_mapping({"name": "Test"})
        self.assertEqual(defaults.language, "en")
        self.assertEqual(defaults.subtitles.get("language"), "en")

    def test_snapshot_preserves_dutch(self) -> None:
        profile = ChannelProductionProfile.from_dict({"language": "nl", "channel_name": "X"})
        self.assertEqual(profile.language, "nl")
        defaults = ChannelDefaults.from_mapping(profile.to_channel_defaults_mapping())
        self.assertEqual(defaults.language, "nl")
        self.assertEqual(defaults.subtitles["language"], "nl")

    def test_studio_general_normalizes(self) -> None:
        general = StudioGeneral.from_dict({"language": "nl-NL"})
        self.assertEqual(general.language, "nl")


class ScenePromptEnglishTests(unittest.TestCase):
    def test_english_passthrough(self) -> None:
        text = "cinematic ice cave, polar mist"
        self.assertEqual(
            ensure_english_scene_prompt(text, language="en", text_provider=None),
            text,
        )

    def test_non_english_without_provider_passthrough(self) -> None:
        text = "ijsgrot bij polar licht"
        self.assertEqual(
            ensure_english_scene_prompt(text, language="nl", text_provider=None),
            text,
        )

    def test_translates_when_provider_available(self) -> None:
        provider = MagicMock()
        provider.generate_text.return_value = "ice cave under polar light"
        result = ensure_english_scene_prompt(
            "ijsgrot bij polar licht",
            language="nl",
            text_provider=provider,
        )
        self.assertEqual(result, "ice cave under polar light")
        provider.generate_text.assert_called_once()


class VoiceFilterTests(unittest.TestCase):
    def test_filter_dutch_only(self) -> None:
        voices = [
            VoiceInfo("a", "Sarah", "en-US"),
            VoiceInfo("b", "Emma", "nl-NL"),
            VoiceInfo("c", "Anna", "nl"),
        ]
        dutch = [
            v for v in voices if voice_matches_language(v.language, "nl")
        ]
        self.assertEqual([v.name for v in dutch], ["Emma", "Anna"])


class ChannelLanguagePropertyTests(unittest.TestCase):
    def test_channel_language_default_english(self) -> None:
        from app.channels.models import Channel

        channel = Channel.create_default("Demo")
        self.assertEqual(channel.language, "en")
        self.assertEqual(channel.language_locale, "en-US")

    def test_channel_language_roundtrip(self) -> None:
        from app.channels.models import Channel

        channel = Channel.create_default("Demo")
        channel.language = "nl"
        raw = channel.to_dict()
        self.assertEqual(raw["language"], "nl")
        self.assertEqual(raw["studio"]["language"], "nl")
        loaded = Channel.from_dict(raw, "Demo")
        self.assertEqual(loaded.language, "nl")
        self.assertEqual(loaded.language_locale, "nl-NL")

    def test_legacy_studio_language_migrates(self) -> None:
        from app.channels.models import Channel

        loaded = Channel.from_dict(
            {
                "name": "Legacy",
                "folder_name": "Legacy",
                "studio": {"language": "de-DE"},
            },
            "Legacy",
        )
        self.assertEqual(loaded.language, "de")

    def test_profile_reads_channel_language(self) -> None:
        from app.channels.models import Channel
        from app.channels.production_profile import ChannelProductionProfile

        channel = Channel.create_default("Demo")
        channel.language = "fr"
        profile = ChannelProductionProfile.from_channel(channel)
        self.assertEqual(profile.language, "fr")
        defaults = ChannelDefaults.from_channel(channel)
        self.assertEqual(defaults.language, "fr")


if __name__ == "__main__":
    unittest.main()
