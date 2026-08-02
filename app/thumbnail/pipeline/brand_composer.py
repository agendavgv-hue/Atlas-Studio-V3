"""Brand Composer — Atlas adds logo, frame, title after AI using Style DNA."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.channels.studio.service import ChannelStudioService
from app.creative.engine.brief import CreativeBrief
from app.creative.engine.style_profile import StyleProfile
from app.models.thumbnail_dna import ThumbnailDNA
from app.thumbnail.brand_overlay import apply_brand_overlays
from app.thumbnail.intelligence.branding import LogoPlacement, ThumbnailBrandingService
from app.thumbnail.intelligence.settings import ThumbnailStudioSettings
from app.thumbnail.pipeline.plan import ThumbnailPlan
from app.thumbnail.style_dna.layout import TextLayoutSpec, text_layout_from_dna
from app.thumbnail.style_dna.models import ThumbnailStyleDNA
from app.thumbnail.text_overlay import render_thumbnail_text


@dataclass(frozen=True)
class BrandComposerAssets:
    logo_path: Path | None
    frame_path: Path | None
    placement: LogoPlacement | None
    fill_hex: str
    outline_hex: str
    font_family: str
    max_words: int
    text_align_left: bool | None
    text_layout: TextLayoutSpec | None = None
    style_dna: ThumbnailStyleDNA | None = None


class BrandComposer:
    """Resolve Channel Studio brand assets and composite with learned Style DNA."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._studio = ChannelStudioService(self._data_root)
        self._branding = ThumbnailBrandingService()

    def resolve_assets(
        self,
        brief: CreativeBrief,
        plan: ThumbnailPlan,
        *,
        thumbnail_profile: StyleProfile | None = None,
        thumb_dna: ThumbnailDNA | None = None,
        style_dna: ThumbnailStyleDNA | None = None,
    ) -> BrandComposerAssets:
        folder = brief.folder_name or brief.channel_name
        if style_dna is None:
            try:
                from app.thumbnail.style_dna.service import ThumbnailStyleDNAService

                style_dna = ThumbnailStyleDNAService(self._data_root).ensure(folder)
            except Exception:  # noqa: BLE001
                style_dna = None

        logo_rel = brief.brand.thumbnail_logo or brief.brand.logo
        logo_path = self._studio.resolve_asset(folder, logo_rel)
        frame_rel = (
            getattr(brief.brand, "thumbnail_frame", "")
            or str((brief.brand.extras or {}).get("thumbnail_frame") or "")
        ).strip()
        frame_path = (
            self._studio.resolve_asset(folder, frame_rel) if frame_rel else None
        )

        logo_pos = str(brief.thumbnail.logo_position or "auto")
        if logo_pos == "auto":
            if style_dna is not None and style_dna.logo_position:
                logo_pos = style_dna.logo_position
            else:
                logo_pos = plan.logo_area or (
                    thumbnail_profile.logo_bias if thumbnail_profile else "auto"
                )

        logo_size = float(brief.thumbnail.logo_size or 0.12)
        if style_dna is not None and style_dna.logo_scale > 0:
            logo_size = float(style_dna.logo_scale)

        margin_px = 48
        if style_dna is not None:
            # Convert learned margin ratio using typical 1280px width.
            margin_px = max(24, int(1280 * float(style_dna.logo_margin or 0.04)))

        settings = ThumbnailStudioSettings(
            max_words=int(
                (style_dna.average_words if style_dna else 0)
                or brief.thumbnail.max_words
                or 4
            ),
            logo_visible=bool(brief.thumbnail.logo_visible),
            logo_position=logo_pos if logo_pos != "auto" else "auto",
            logo_size=logo_size,
            contrast=str(
                (style_dna.contrast if style_dna else "")
                or brief.thumbnail.contrast
                or "very_high"
            ),
            negative_space=str(
                (style_dna.negative_space if style_dna else "")
                or plan.negative_space
                or "left"
            ),
            creativity=float(brief.thumbnail.creativity or 60),
            style_strength=float(brief.thumbnail.style_strength or 80),
            brand_strength=float(brief.thumbnail.brand_strength or 85),
            safe_margin_px=margin_px,
        )
        placement = self._branding.resolve_logo_placement(
            settings=settings,
            dna=thumb_dna,
            subject_position=(
                (style_dna.subject_position if style_dna else "")
                or (thumbnail_profile.subject_bias if thumbnail_profile else "")
            ),
        )
        if placement is not None and style_dna is not None:
            placement = LogoPlacement(
                position=placement.position,
                size=float(style_dna.logo_scale or placement.size),
                opacity=placement.opacity,
                margin_px=margin_px,
                auto_scaled=placement.auto_scaled,
                reason=f"{placement.reason}|style_dna",
            )

        fill = brief.brand.primary_color or ""
        outline = brief.brand.secondary_color or "#1A1208"
        font = brief.brand.fonts[0] if brief.brand.fonts else ""
        layout = text_layout_from_dna(style_dna)
        align_left: bool | None = None
        if layout is not None:
            align_left = layout.align_left
        elif plan.negative_space:
            align_left = plan.negative_space != "right"
        elif thumbnail_profile is not None:
            align_left = thumbnail_profile.text_position != "right"

        max_words = int(brief.thumbnail.max_words or 4)
        if style_dna is not None:
            max_words = max(max_words, int(style_dna.text_max_lines or max_words))

        return BrandComposerAssets(
            logo_path=logo_path,
            frame_path=frame_path,
            placement=placement,
            fill_hex=fill,
            outline_hex=outline,
            font_family=font,
            max_words=max_words,
            text_align_left=align_left,
            text_layout=layout,
            style_dna=style_dna,
        )

    def compose(
        self,
        image_png: bytes,
        *,
        hook: str,
        channel_name: str,
        assets: BrandComposerAssets,
    ) -> bytes:
        """Apply frame + logo + typography from Style DNA + Channel Studio."""
        composed = apply_brand_overlays(
            image_png,
            logo_path=assets.logo_path,
            frame_path=assets.frame_path,
            placement=assets.placement,
        )
        return render_thumbnail_text(
            composed,
            hook,
            channel_name=channel_name,
            fill_hex=assets.fill_hex,
            outline_hex=assets.outline_hex,
            font_family=assets.font_family,
            align_left=assets.text_align_left,
            max_words=assets.max_words,
            layout=assets.text_layout,
        )

    def auto_adjust_assets(
        self,
        assets: BrandComposerAssets,
        *,
        critic_scores: dict[str, float],
    ) -> BrandComposerAssets:
        """Light automatic adjustments when critic flags readability/branding."""
        placement = assets.placement
        if placement is None:
            return assets
        readability = float(critic_scores.get("readability", 100))
        brand = float(critic_scores.get("brand_consistency", 100))
        size = float(placement.size)
        if brand < 85:
            size = min(0.22, size * 1.15)
        if readability < 85:
            size = max(0.08, size * 0.92)
        new_placement = LogoPlacement(
            position=placement.position,
            size=size,
            opacity=placement.opacity,
            margin_px=max(24, placement.margin_px),
            auto_scaled=placement.auto_scaled,
            reason=f"{placement.reason}|auto_adjust",
        )
        return BrandComposerAssets(
            logo_path=assets.logo_path,
            frame_path=assets.frame_path,
            placement=new_placement,
            fill_hex=assets.fill_hex,
            outline_hex=assets.outline_hex,
            font_family=assets.font_family,
            max_words=assets.max_words,
            text_align_left=assets.text_align_left,
            text_layout=assets.text_layout,
            style_dna=assets.style_dna,
        )
