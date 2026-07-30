"""VoiceExporter — write the finished narration file only.

Receives finished WAV bytes and writes ``voice/voice.wav``.
Does not plan, synthesize, concatenate, mutate audio, or write manifests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.voice.naming import voice_path


@dataclass(frozen=True)
class VoiceExportResult:
    """Outcome of a single WAV export."""

    path: Path
    bytes_written: int


class VoiceExporter:
    """Project-facing file writer for the canonical narration WAV."""

    def export_wav(self, project_dir: Path, audio_wav: bytes) -> VoiceExportResult:
        """Write ``audio_wav`` to ``voice/voice.wav``.

        Raises:
            ValueError: if ``audio_wav`` is empty.
            OSError: if the file cannot be written.
        """
        if not audio_wav:
            raise ValueError("Cannot export an empty voice narration.")

        path = voice_path(project_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio_wav)
        return VoiceExportResult(path=path, bytes_written=len(audio_wav))
