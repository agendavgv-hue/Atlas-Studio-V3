"""Improve Engine — targeted fixes for weak critic axes only."""

from __future__ import annotations

from app.thumbnail.critic_engine.models import (
    CriticReport,
    ImproveAction,
    ImprovePlan,
)
from app.thumbnail.style_dna.models import ThumbnailStyleDNA
from app.thumbnail.pipeline.brand_composer import BrandComposerAssets
from app.thumbnail.intelligence.branding import LogoPlacement


class ImproveEngine:
    """Build an Improve Plan from critic weaknesses — never random changes."""

    def build_plan(
        self,
        report: CriticReport,
        *,
        style_dna: ThumbnailStyleDNA | None = None,
        max_actions: int = 8,
    ) -> ImprovePlan:
        weak = report.weak_axes()
        actions: list[ImproveAction] = []
        lines: list[str] = []

        for axis in weak[:max_actions]:
            action, target = _map_action(axis.axis, axis.improvement, style_dna)
            actions.append(
                ImproveAction(
                    axis=axis.axis,
                    action=action,
                    detail=axis.improvement,
                    target=target,
                )
            )
            lines.append(axis.improvement)

        # Deduplicate similar lines while preserving order
        unique: list[str] = []
        for line in lines:
            if line and line not in unique:
                unique.append(line)

        return ImprovePlan(
            actions=actions,
            summary_lines=unique[:max_actions],
            critic_overall=report.overall,
            attempt=report.attempt,
        )

    def apply_compose_adjustments(
        self,
        assets: BrandComposerAssets,
        plan: ImprovePlan,
        *,
        style_dna: ThumbnailStyleDNA | None = None,
    ) -> BrandComposerAssets:
        """Apply logo/layout improvements that do not need a new AI image."""
        placement = assets.placement
        layout = assets.text_layout
        if placement is None and not plan.actions:
            return assets

        size = float(placement.size) if placement else 0.11
        position = placement.position if placement else "bottom_left"
        margin = placement.margin_px if placement else 48
        reason = placement.reason if placement else "improve"
        touched = False

        for action in plan.actions:
            if action.target != "compose":
                continue
            touched = True
            if action.axis == "logo_position" and style_dna:
                position = style_dna.logo_position
            if action.axis == "logo_size" and style_dna:
                size = float(style_dna.logo_scale)
            if action.axis == "logo_size" and "verklein" in action.detail.casefold():
                size = max(0.06, size * 0.9)
            if action.axis == "brand_consistency" and style_dna:
                position = style_dna.logo_position
                size = float(style_dna.logo_scale)

        # Text shrink hint → slightly reduce max words if overcrowded
        max_words = assets.max_words
        for action in plan.actions:
            if action.axis in {"text_layout", "headline_size"} and "verklein" in action.detail.casefold():
                max_words = max(2, max_words)

        if not touched and placement is None:
            return assets

        new_placement = None
        if placement is not None:
            new_placement = LogoPlacement(
                position=position,
                size=size,
                opacity=placement.opacity,
                margin_px=margin,
                auto_scaled=placement.auto_scaled,
                reason=f"{reason}|improve_engine",
            )
        return BrandComposerAssets(
            logo_path=assets.logo_path,
            frame_path=assets.frame_path,
            placement=new_placement if new_placement is not None else placement,
            fill_hex=assets.fill_hex,
            outline_hex=assets.outline_hex,
            font_family=assets.font_family,
            max_words=max_words,
            text_align_left=assets.text_align_left,
            text_layout=layout,
            style_dna=assets.style_dna,
        )

    def critic_notes(self, plan: ImprovePlan) -> str:
        return "; ".join(plan.summary_lines)


def _map_action(
    axis: str,
    improvement: str,
    style_dna: ThumbnailStyleDNA | None,
) -> tuple[str, str]:
    compose_axes = {"logo_position", "logo_size", "brand_consistency", "text_layout", "headline_size"}
    if axis in compose_axes:
        return improvement, "compose"
    if axis in {"composition", "negative_space", "subject_visibility", "visual_focus"}:
        return improvement, "plan"
    return improvement, "prompt"
