"""Thumbnail branding — Brand Kit + auto logo positioning architecture."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.creative.models.brand_kit import BrandKit
from app.models.thumbnail_dna import ThumbnailDNA
from app.thumbnail.intelligence.settings import ThumbnailStudioSettings


@dataclass(frozen=True)
class LogoPlacement:
    """Resolved logo placement for overlay / future auto engine."""

    position: str  # top_left|top_right|bottom_left|bottom_right|center
    size: float
    opacity: float
    margin_px: int
    auto_scaled: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ThumbnailBrandingService:
    """Apply Brand Kit rules; prepare auto-positioning (architecture ready)."""

    def resolve_logo_placement(
        self,
        *,
        settings: ThumbnailStudioSettings,
        dna: ThumbnailDNA | None = None,
        subject_position: str = "",
    ) -> LogoPlacement | None:
        if not settings.logo_visible:
            return None

        subject = (subject_position or "").strip().casefold()
        if not subject and dna is not None:
            subject = (dna.layout.subject_position or "right").casefold()

        if settings.logo_position == "auto":
            position = self.auto_position(subject)
            reason = f"auto from subject={subject or 'right'}"
        else:
            position = settings.logo_position
            reason = "user setting"

        size = float(settings.logo_size)
        if settings.auto_scale_logo and dna is not None:
            # Keep logo subordinate to hero scale from DNA.
            if (dna.logo.size or "").casefold() == "small":
                size = min(size, 0.10)
            elif (dna.logo.size or "").casefold() == "large":
                size = max(size, 0.16)

        return LogoPlacement(
            position=position,
            size=size,
            opacity=float(settings.logo_opacity),
            margin_px=int(settings.safe_margin_px),
            auto_scaled=bool(settings.auto_scale_logo),
            reason=reason,
        )

    @staticmethod
    def auto_position(subject_position: str) -> str:
        """Architecture for later AI auto-placement.

        Subject right → logo left (bottom)
        Subject left  → logo right (bottom)
        Subject center → logo bottom (bottom_left as default safe)
        """
        key = (subject_position or "right").casefold()
        if key in {"right", "far_right"}:
            return "bottom_left"
        if key in {"left", "far_left"}:
            return "bottom_right"
        if key in {"center", "middle"}:
            return "bottom_left"
        return "bottom_left"

    def branding_prompt_block(
        self,
        brand: BrandKit | None,
        *,
        settings: ThumbnailStudioSettings,
        placement: LogoPlacement | None,
    ) -> str:
        if brand is None:
            return ""
        strength = settings.brand_strength / 100.0
        colors = [
            c
            for c in (brand.primary_color, brand.secondary_color, brand.accent_color)
            if c
        ]
        parts = [
            f"brand strength {strength:.2f}",
            f"palette {' / '.join(colors)}" if colors else "",
        ]
        if placement is not None and settings.logo_visible:
            parts.append(
                f"logo {placement.position} size={placement.size:.2f} "
                f"opacity={placement.opacity:.2f} margin={placement.margin_px}px"
            )
            if brand.thumbnail_logo or brand.logo:
                parts.append("reserve clear space for channel logo overlay (do not paint logo)")
        return "branding: " + "; ".join(p for p in parts if p)
