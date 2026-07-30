"""Unit tests for VoicePlanner (Sprint 11 component 3)."""

from __future__ import annotations

import unittest

from app.core.voice_settings import VoiceSettings
from app.voice.manifest import VoiceManifest
from app.voice.plan import VoicePlan
from app.voice.planner import VoicePlanner


class VoicePlannerTests(unittest.TestCase):
    def test_defaults_to_single_segment_list(self) -> None:
        plan = VoicePlanner().plan("Hello Atlas Studio.")
        self.assertIsInstance(plan, VoicePlan)
        self.assertIsInstance(plan.segments, tuple)
        self.assertEqual(len(plan.segments), 1)
        self.assertEqual(plan.count, 1)
        self.assertEqual(plan.segments[0].index, 1)
        self.assertEqual(plan.segments[0].text, "Hello Atlas Studio.")
        self.assertEqual(plan.full_text, "Hello Atlas Studio.")
        self.assertEqual(plan.language, "en-US")
        self.assertIsNotNone(plan.estimated_duration_sec)
        self.assertGreater(plan.estimated_duration_sec or 0.0, 0.0)
        self.assertIn("Single full-script", plan.rationale)

    def test_segments_always_list_shaped_api(self) -> None:
        plan = VoicePlanner().plan("One.")
        # API contract: always an ordered collection, never a bare string field.
        self.assertEqual(type(plan.segments), tuple)
        self.assertEqual(list(plan.segments)[0].text, "One.")

    def test_placeholder_fields_reserved(self) -> None:
        segment = VoicePlanner().plan("Narration text.").segments[0]
        self.assertEqual(segment.pause_after_sec, 0.0)
        self.assertEqual(segment.emphasis, "")
        self.assertEqual(segment.emotion, "")
        self.assertEqual(segment.speaker, "")

    def test_deterministic_for_same_script_and_settings(self) -> None:
        settings = VoiceSettings(language="en-GB", speed=1.25)
        first = VoicePlanner(settings).plan("  Same script every time.  ")
        second = VoicePlanner(settings).plan("  Same script every time.  ")
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.language, "en-GB")
        self.assertEqual(first.estimated_duration_sec, second.estimated_duration_sec)

    def test_speed_affects_estimated_duration_deterministically(self) -> None:
        script = "Word " * 150  # ~150 words → ~60s at 1.0x
        slow = VoicePlanner(VoiceSettings(speed=1.0)).plan(script)
        fast = VoicePlanner(VoiceSettings(speed=2.0)).plan(script)
        self.assertAlmostEqual(slow.estimated_duration_sec or 0.0, 60.0, places=2)
        self.assertAlmostEqual(fast.estimated_duration_sec or 0.0, 30.0, places=2)

    def test_rejects_empty_script(self) -> None:
        with self.assertRaises(ValueError):
            VoicePlanner().plan("")
        with self.assertRaises(ValueError):
            VoicePlanner().plan("   \n\t  ")

    def test_plan_feeds_manifest_for_generator(self) -> None:
        """Generator will read VoiceManifest built from this plan — not the plan live."""
        plan = VoicePlanner().plan("Ready for synthesis.")
        manifest = VoiceManifest.from_plan(
            plan,
            provider_id="kokoro",
            voice_id="af_heart",
            speed=1.0,
        )
        self.assertEqual(len(manifest.segments), 1)
        self.assertEqual(manifest.segments[0].text, plan.segments[0].text)
        self.assertEqual(manifest.estimated_duration_sec, plan.estimated_duration_sec)
        self.assertEqual(manifest.rationale, plan.rationale)
        self.assertEqual(manifest.full_text, plan.full_text)


if __name__ == "__main__":
    unittest.main()
