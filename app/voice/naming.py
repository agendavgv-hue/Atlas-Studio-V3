"""Output naming and folder resolution for voice narration.

New projects always write under ``voice/``. Discovery prefers
``voice/`` then legacy ``mp3/`` then ``audio/`` (via Artifact Resolver).
"""

from __future__ import annotations

from pathlib import Path

VOICE_FOLDER = "voice"
LEGACY_MP3_FOLDER = "mp3"
LEGACY_AUDIO_FOLDER = "audio"
VOICE_BASENAME = "voice.wav"
MANIFEST_BASENAME = "voice_manifest.json"

# Discovery order — must match ArtifactRule.folders for VOICE.
VOICE_DISCOVERY_FOLDERS: tuple[str, ...] = (
    VOICE_FOLDER,
    LEGACY_MP3_FOLDER,
    LEGACY_AUDIO_FOLDER,
)


def voice_basename() -> str:
    return VOICE_BASENAME


def manifest_basename() -> str:
    return MANIFEST_BASENAME


def resolve_voice_dir(project_dir: Path) -> Path:
    """Canonical write folder for new voice exports — always ``voice/``."""
    folder = project_dir.expanduser().resolve() / VOICE_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def voice_path(project_dir: Path) -> Path:
    """Canonical exported narration — ``voice/voice.wav``."""
    return resolve_voice_dir(project_dir) / VOICE_BASENAME


def voice_manifest_path(project_dir: Path) -> Path:
    """Durable plan written beside the narration."""
    return resolve_voice_dir(project_dir) / MANIFEST_BASENAME
