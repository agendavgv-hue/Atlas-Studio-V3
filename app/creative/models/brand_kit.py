"""Brand Kit — logos, colors, fonts, intro/outro/CTA assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.creative.models._util import from_dict, to_dict


@dataclass
class BrandKit:
    logo: str = ""
    watermark: str = ""
    thumbnail_logo: str = ""
    thumbnail_frame: str = ""
    banner: str = ""
    fonts: list[str] = field(default_factory=list)
    primary_color: str = ""
    secondary_color: str = ""
    accent_color: str = ""
    intro: str = ""
    outro: str = ""
    cta: str = ""
    social_branding: dict[str, str] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BrandKit:
        return from_dict(cls, data)
