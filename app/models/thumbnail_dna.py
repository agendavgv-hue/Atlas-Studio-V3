"""Thumbnail DNA — learned visual style profile for one channel."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ThumbnailLayoutDNA:
    title_position: str = "left"
    subject_position: str = "right"
    logo_position: str = "bottom_left"
    negative_space: str = "left"


@dataclass
class ThumbnailTextDNA:
    title_size: str = "huge"
    average_words: float = 4.0
    title_alignment: str = "left"


@dataclass
class ThumbnailColorDNA:
    primary: str = "#d4af37"
    secondary: str = "#0b0b0b"
    accent: str = "#ffffff"
    contrast: str = "very_high"
    brightness: str = "dark"
    saturation: str = "medium"


@dataclass
class ThumbnailStyleDNA:
    contrast: str = "very_high"
    lighting: str = "dark_cinematic"
    emotion: str = "mystery"
    genre: str = "cinematic"
    atmosphere: str = "premium"


@dataclass
class ThumbnailCompositionDNA:
    subject_count: str = "one"
    subject_scale: str = "large"
    focus: str = "hero"
    gaze_direction: str = "into_frame"


@dataclass
class ThumbnailLogoDNA:
    position: str = "bottom_left"
    size: str = "small"


@dataclass
class ThumbnailTypographyDNA:
    title_size: str = "huge"
    weight: str = "bold"
    max_words: int = 4
    outline: str = "strong"
    safe_from_logo: bool = True


@dataclass
class ThumbnailSpacingDNA:
    negative_space: str = "left"
    margin: str = "safe"
    subject_padding: str = "medium"


@dataclass
class ThumbnailSafeAreasDNA:
    left: str = "headline"
    right: str = "subject"
    top: str = "clear"
    bottom: str = "logo_ok"
    margin_px: int = 48


@dataclass
class ThumbnailDNA:
    """Extensible per-channel thumbnail style learned from references."""

    channel_id: str = ""
    channel_name: str = ""
    version: int = 2
    reference_count: int = 0
    layout: ThumbnailLayoutDNA = field(default_factory=ThumbnailLayoutDNA)
    text: ThumbnailTextDNA = field(default_factory=ThumbnailTextDNA)
    colors: ThumbnailColorDNA = field(default_factory=ThumbnailColorDNA)
    style: ThumbnailStyleDNA = field(default_factory=ThumbnailStyleDNA)
    composition: ThumbnailCompositionDNA = field(default_factory=ThumbnailCompositionDNA)
    logo: ThumbnailLogoDNA = field(default_factory=ThumbnailLogoDNA)
    typography: ThumbnailTypographyDNA = field(default_factory=ThumbnailTypographyDNA)
    spacing: ThumbnailSpacingDNA = field(default_factory=ThumbnailSpacingDNA)
    safe_areas: ThumbnailSafeAreasDNA = field(default_factory=ThumbnailSafeAreasDNA)
    # Forward-compatible bag for future keys without schema bumps.
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "version": self.version,
            "reference_count": self.reference_count,
            "layout": asdict(self.layout),
            "text": asdict(self.text),
            "colors": asdict(self.colors),
            "style": asdict(self.style),
            "composition": asdict(self.composition),
            "logo": asdict(self.logo),
            "typography": asdict(self.typography),
            "spacing": asdict(self.spacing),
            "safe_areas": asdict(self.safe_areas),
        }
        if self.extras:
            payload["extras"] = dict(self.extras)
        return payload

    def prompt_block(self) -> str:
        """Compact style guidance for image prompts (style only, not content)."""
        return (
            f"thumbnail style DNA: title {self.layout.title_position}, "
            f"subject {self.layout.subject_position}, "
            f"negative space {self.layout.negative_space}, "
            f"title size {self.text.title_size}, "
            f"~{self.text.average_words:g} words, "
            f"colors {self.colors.primary}/{self.colors.secondary}, "
            f"contrast {self.style.contrast}, lighting {self.style.lighting}, "
            f"emotion {self.style.emotion}, genre {self.style.genre}, "
            f"subject scale {self.composition.subject_scale}, "
            f"logo {self.logo.position} {self.logo.size}"
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ThumbnailDNA:
        raw = dict(data or {})
        # Promote unknown top-level keys into extras.
        known = {
            "channel_id",
            "channel_name",
            "version",
            "reference_count",
            "layout",
            "text",
            "colors",
            "style",
            "composition",
            "logo",
            "typography",
            "spacing",
            "safe_areas",
            "extras",
        }
        extras = dict(raw.get("extras") or {}) if isinstance(raw.get("extras"), dict) else {}
        for key, value in raw.items():
            if key not in known:
                extras[key] = value
        return cls(
            channel_id=str(raw.get("channel_id") or "").strip(),
            channel_name=str(raw.get("channel_name") or "").strip(),
            version=int(raw.get("version") or 2),
            reference_count=int(raw.get("reference_count") or 0),
            layout=_section(ThumbnailLayoutDNA, raw.get("layout")),
            text=_section(ThumbnailTextDNA, raw.get("text")),
            colors=_section(ThumbnailColorDNA, raw.get("colors")),
            style=_section(ThumbnailStyleDNA, raw.get("style")),
            composition=_section(ThumbnailCompositionDNA, raw.get("composition")),
            logo=_section(ThumbnailLogoDNA, raw.get("logo")),
            typography=_section(ThumbnailTypographyDNA, raw.get("typography")),
            spacing=_section(ThumbnailSpacingDNA, raw.get("spacing")),
            safe_areas=_section(ThumbnailSafeAreasDNA, raw.get("safe_areas")),
            extras=extras,
        )


def _section(cls: type, data: Any):
    if not isinstance(data, dict):
        return cls()
    fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    kwargs = {}
    for key in fields:
        if key not in data:
            continue
        value = data[key]
        if key in {"average_words"}:
            try:
                kwargs[key] = float(value)
            except (TypeError, ValueError):
                kwargs[key] = 4.0
        elif key in {"max_words", "margin_px"}:
            try:
                kwargs[key] = int(value)
            except (TypeError, ValueError):
                continue
        elif key in {"safe_from_logo"}:
            kwargs[key] = bool(value)
        else:
            kwargs[key] = str(value).strip() if value is not None else getattr(cls(), key)
    return cls(**kwargs)
