"""Generated Channel DNA profile for AI Channel Creator (new channels only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GeneratedChannelProfile:
    """Complete identity pack for a newly created channel."""

    name: str
    description: str = ""
    image_prompt: str = ""
    negative_prompt: str = ""
    thumbnail_prompt: str = ""
    outro_line: str = ""
    voice: dict[str, Any] = field(default_factory=dict)
    # Thumbnail DNA pack (channel_dna.json entry shape).
    dna: dict[str, Any] = field(default_factory=dict)
    # Thumbnail style pack (channel_style.json entry shape).
    style: dict[str, Any] = field(default_factory=dict)

    def to_channel_fields(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "image_prompt": self.image_prompt,
            "negative_prompt": self.negative_prompt,
            "thumbnail_prompt": self.thumbnail_prompt,
            "outro_line": self.outro_line,
            "voice": dict(self.voice or {}),
        }
