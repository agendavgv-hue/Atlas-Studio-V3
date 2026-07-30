"""Unit tests for Voice naming / plan / manifest + VOICE discovery (Sprint 11 component 1)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.artifacts import ArtifactKind, ArtifactResolver
from app.voice.manifest import VoiceManifest
from app.voice.naming import (
    MANIFEST_BASENAME,
    VOICE_BASENAME,
    VOICE_FOLDER,
    voice_manifest_path,
    voice_path,
)
from app.voice.plan import VoicePlan, VoiceSegment


class VoiceNamingTests(unittest.TestCase):
    def test_canonical_write_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(voice_path(root).name, VOICE_BASENAME)
            self.assertEqual(voice_path(root).parent.name, VOICE_FOLDER)
            self.assertEqual(voice_manifest_path(root).name, MANIFEST_BASENAME)
            self.assertTrue(voice_path(root).parent.is_dir())


class VoiceManifestTests(unittest.TestCase):
    def test_from_plan_round_trip(self) -> None:
        plan = VoicePlan(
            segments=(
                VoiceSegment(index=1, text="Hello Atlas."),
            ),
            language="en-US",
            estimated_duration_sec=2.5,
            rationale="Single segment",
        )
        manifest = VoiceManifest.from_plan(
            plan,
            provider_id="kokoro",
            voice_id="af_heart",
            voice_name="Heart",
            speed=1.0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = voice_manifest_path(Path(tmp))
            manifest.write_json(path)
            loaded = VoiceManifest.read_json(path)
            self.assertEqual(loaded.provider_id, "kokoro")
            self.assertEqual(loaded.full_text, "Hello Atlas.")
            self.assertEqual(loaded.output.filename, VOICE_BASENAME)
            self.assertEqual(loaded.output.folder, VOICE_FOLDER)
            self.assertFalse(loaded.exported)
            self.assertEqual(loaded.segments[0].text, "Hello Atlas.")


class VoiceDiscoveryTests(unittest.TestCase):
    def test_prefers_voice_folder_over_legacy_mp3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mp3").mkdir()
            (root / "voice").mkdir()
            (root / "mp3" / "voice.mp3").write_bytes(b"legacy")
            (root / "voice" / "voice.wav").write_bytes(b"modern")
            found = ArtifactResolver(root).find(ArtifactKind.VOICE)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.parent.name, "voice")
            self.assertEqual(found.name, "voice.wav")

    def test_falls_back_to_mp3_then_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mp3").mkdir()
            (root / "mp3" / "voice.mp3").write_bytes(b"legacy")
            found = ArtifactResolver(root).find(ArtifactKind.VOICE)
            self.assertEqual(found.name, "voice.mp3")  # type: ignore[union-attr]

            (root / "mp3" / "voice.mp3").unlink()
            (root / "audio").mkdir()
            (root / "audio" / "narration.wav").write_bytes(b"older")
            found = ArtifactResolver(root).find(ArtifactKind.VOICE)
            self.assertEqual(found.parent.name, "audio")  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
