"""Standard voice output names and folder resolution."""

from __future__ import annotations

from pathlib import Path

# V3 write target — discovery still uses ArtifactResolver (mp3/ + audio/).
MP3_FOLDER = "mp3"
LEGACY_AUDIO_FOLDER = "audio"
VOICE_BASENAME = "voice.mp3"
VOICE_BASENAME_WAV = "voice.wav"


def voice_basename(content_type: str = "audio/mpeg") -> str:
    """Canonical generated narration filename from provider content type."""
    kind = (content_type or "").casefold()
    if "wav" in kind or "wave" in kind:
        return VOICE_BASENAME_WAV
    return VOICE_BASENAME


def resolve_mp3_dir(project_dir: Path) -> Path:
    """Resolve the project voice output folder.

    Rules:
    - If ``mp3/`` exists → use it
    - Else if ``audio/`` exists → use it (legacy / alternate)
    - Else → create ``mp3/``
    """
    root = project_dir.expanduser().resolve()
    standard = root / MP3_FOLDER
    legacy = root / LEGACY_AUDIO_FOLDER
    if standard.is_dir():
        return standard
    if legacy.is_dir():
        return legacy
    standard.mkdir(parents=True, exist_ok=True)
    return standard
