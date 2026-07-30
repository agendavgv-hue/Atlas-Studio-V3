"""Purpose-based rules for locating project artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from app.artifacts.kinds import ArtifactKind

DOCUMENT_EXTENSIONS = frozenset({".txt", ".md", ".docx", ".rtf", ".doc"})
SHEET_EXTENSIONS = frozenset({".csv", ".xlsx", ".xls", ".tsv", ".json"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".wma"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"})

IGNORE_FILENAMES = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})


@dataclass(frozen=True)
class ArtifactRule:
    """How to locate one artifact purpose inside a project."""

    kind: ArtifactKind
    folders: tuple[str, ...]
    extensions: frozenset[str]
    name_hints: tuple[str, ...] = ()
    # When True, any matching extension in the folders qualifies (name hints only affect rank).
    any_matching_file: bool = False
    # Extensions that match by type alone (no name hint required).
    type_only_extensions: frozenset[str] = frozenset()


ARTIFACT_RULES: dict[ArtifactKind, ArtifactRule] = {
    ArtifactKind.SCRIPT: ArtifactRule(
        kind=ArtifactKind.SCRIPT,
        folders=("script",),
        extensions=DOCUMENT_EXTENSIONS,
        name_hints=("script", "screenplay", "story"),
        # Prefer hint names; still accept other docs in script/ for V2/renamed files.
        any_matching_file=True,
    ),
    ArtifactKind.PRODUCTION_SHEET: ArtifactRule(
        kind=ArtifactKind.PRODUCTION_SHEET,
        folders=("script",),
        extensions=DOCUMENT_EXTENSIONS | SHEET_EXTENSIONS,
        name_hints=("production", "sheet", "scene"),
        type_only_extensions=SHEET_EXTENSIONS,
    ),
    ArtifactKind.IMAGES: ArtifactRule(
        kind=ArtifactKind.IMAGES,
        folders=("images", "image"),
        extensions=IMAGE_EXTENSIONS,
        any_matching_file=True,
    ),
    ArtifactKind.VOICE: ArtifactRule(
        kind=ArtifactKind.VOICE,
        # Prefer modern voice/; keep mp3/ and audio/ as legacy read fallbacks.
        folders=("voice", "mp3", "audio"),
        extensions=AUDIO_EXTENSIONS,
        name_hints=("voice", "narration", "audio"),
        any_matching_file=True,
    ),
    ArtifactKind.THUMBNAIL: ArtifactRule(
        kind=ArtifactKind.THUMBNAIL,
        folders=("thumbnail",),
        extensions=IMAGE_EXTENSIONS,
        name_hints=("thumbnail", "thumb"),
        any_matching_file=True,
    ),
    ArtifactKind.YOUTUBE_EXPORT: ArtifactRule(
        kind=ArtifactKind.YOUTUBE_EXPORT,
        folders=("youtube_video",),
        extensions=VIDEO_EXTENSIONS,
        any_matching_file=True,
    ),
}
