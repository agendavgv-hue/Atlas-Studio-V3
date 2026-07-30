"""Unit tests for VoiceExporter (Sprint 11 component 2)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.voice.exporter import VoiceExporter
from app.voice.naming import VOICE_BASENAME, VOICE_FOLDER, voice_path


class VoiceExporterTests(unittest.TestCase):
    def test_writes_canonical_wav_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"RIFF....WAVEfmt "
            result = VoiceExporter().export_wav(root, payload)

            expected = voice_path(root)
            self.assertEqual(result.path, expected)
            self.assertEqual(result.path.name, VOICE_BASENAME)
            self.assertEqual(result.path.parent.name, VOICE_FOLDER)
            self.assertEqual(result.bytes_written, len(payload))
            self.assertEqual(expected.read_bytes(), payload)

            names = {path.name for path in expected.parent.iterdir() if path.is_file()}
            self.assertEqual(names, {VOICE_BASENAME})

    def test_overwrites_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = voice_path(root)
            path.write_bytes(b"old")
            VoiceExporter().export_wav(root, b"new-wav")
            self.assertEqual(path.read_bytes(), b"new-wav")

    def test_rejects_empty_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                VoiceExporter().export_wav(Path(tmp), b"")


if __name__ == "__main__":
    unittest.main()
