"""Intelligence context — Creative Director + Brand + Style + DNA + Studio."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.creative.models.brand_kit import BrandKit
from app.creative.models.director import CreativeDirector
from app.creative.models.style_library import StyleLibrary
from app.creative.services.director_service import CreativeDirectorService
from app.models.thumbnail_dna import ThumbnailDNA
from app.services.thumbnail_dna_service import ThumbnailDNAService
from app.thumbnail.intelligence.branding import LogoPlacement, ThumbnailBrandingService
from app.thumbnail.intelligence.settings import (
    ThumbnailStudioSettings,
    ThumbnailStudioSettingsStore,
)


@dataclass
class ThumbnailIntelligenceContext:
    channel: str
    studio: ThumbnailStudioSettings
    director: CreativeDirector | None
    brand: BrandKit | None
    style: StyleLibrary | None
    dna: ThumbnailDNA | None
    reference_count: int = 0
    logo_placement: LogoPlacement | None = None

    def identity_brief(self) -> str:
        parts: list[str] = []
        if self.director is not None:
            parts.extend(self.director.rule_summaries()[:6])
            thumb = self.director.thumbnail
            parts.append(
                f"director thumb: layout {thumb.layout}, text {thumb.text_position}, "
                f"max_words {thumb.max_words}, ctr {thumb.ctr_style}"
            )
            parts.append(
                f"visual: {self.director.visual.lighting}, {self.director.visual.contrast}, "
                f"{self.director.visual.color_palette}"
            )
        if self.style is not None:
            parts.append(
                f"style library: realism {self.style.realism:g}, mystery {self.style.mystery:g}, "
                f"thumb {self.style.thumbnail_style}, lighting {self.style.lighting}"
            )
        if self.dna is not None:
            parts.append(self.dna.prompt_block())
        parts.append(
            f"studio: style_strength {self.studio.style_strength:g}, "
            f"brand_strength {self.studio.brand_strength:g}, "
            f"max_words {self.studio.max_words}, contrast {self.studio.contrast}"
        )
        return "\n".join(p for p in parts if p)

    def to_critic_payload(self, *, hook: str = "", prompt: str = "") -> dict[str, Any]:
        dna = self.dna
        placement = self.logo_placement
        return {
            "hook": hook,
            "prompt": prompt,
            "title_position": (
                dna.layout.title_position if dna else self.studio.negative_space
            ),
            "subject_position": dna.layout.subject_position if dna else "right",
            "subject_scale": dna.composition.subject_scale if dna else "large",
            "subject_count": 1,
            "contrast": self.studio.contrast,
            "primary_color": (self.brand.primary_color if self.brand else "")
            or (dna.colors.primary if dna else ""),
            "logo_size": "small" if placement and placement.size < 0.15 else "medium",
            "layout": dna.layout.title_position if dna else self.studio.negative_space,
        }


def load_intelligence_context(
    data_root: Path,
    channel: str,
    *,
    text_provider: Any | None = None,
) -> ThumbnailIntelligenceContext:
    studio = ThumbnailStudioSettingsStore(data_root).load(channel)
    director = brand = style = None
    try:
        creative = CreativeDirectorService(data_root)
        director = creative.ensure(channel)
        brand = creative.get_brand(channel)
        style = creative.get_style(channel)
        # Sync studio max_words into director thumbnail rules when user set them.
        if director.thumbnail.max_words != studio.max_words:
            director.thumbnail.max_words = studio.max_words
    except Exception:  # noqa: BLE001
        pass

    dna = ThumbnailDNAService(data_root).get_thumbnail_dna(channel)
    reference_count = 0
    try:
        from app.services.thumbnail_reference_service import ThumbnailReferenceService

        reference_count = ThumbnailReferenceService(
            data_root, text_provider=text_provider
        ).reference_count(channel)
    except Exception:  # noqa: BLE001
        reference_count = 0
    branding = ThumbnailBrandingService()
    placement = branding.resolve_logo_placement(
        settings=studio,
        dna=dna,
        subject_position=(dna.layout.subject_position if dna else "right"),
    )
    return ThumbnailIntelligenceContext(
        channel=channel.strip(),
        studio=studio,
        director=director,
        brand=brand,
        style=style,
        dna=dna,
        reference_count=reference_count,
        logo_placement=placement,
    )
