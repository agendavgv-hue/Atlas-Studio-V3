"""Persist thumbnail_style_profile.json (Style DNA)."""

from __future__ import annotations

import json
from pathlib import Path

from app.thumbnail.style_dna.models import ThumbnailStyleDNA

STYLE_PROFILE_BASENAME = "thumbnail_style_profile.json"


def write_style_dna(path: Path, dna: ThumbnailStyleDNA) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dna.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def read_style_dna(path: Path) -> ThumbnailStyleDNA | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return ThumbnailStyleDNA.from_dict(raw)
