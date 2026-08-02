"""Layout Critic — score design candidates against the scene map + Style DNA."""

from __future__ import annotations

from app.thumbnail.design_engine.models import (
    DesignScores,
    LayoutCandidate,
    RectNorm,
    SceneMap,
)
from app.thumbnail.style_dna.models import ThumbnailStyleDNA


class LayoutCritic:
    def score(
        self,
        layout: LayoutCandidate,
        *,
        scene: SceneMap,
        style_dna: ThumbnailStyleDNA | None = None,
    ) -> DesignScores:
        notes: list[str] = []
        text = layout.text_rect
        subject = scene.subject
        focus = RectNorm(
            x=max(0.0, scene.focus_x - 0.06),
            y=max(0.0, scene.focus_y - 0.06),
            w=0.12,
            h=0.12,
        )
        horizon = RectNorm(x=0.0, y=max(0.0, scene.horizon_y - 0.04), w=1.0, h=0.08)

        composition = 78.0
        if text.overlaps(subject, pad=0.01):
            composition -= 28.0
            notes.append("Tekst bedekt onderwerp")
        else:
            composition += 8.0
        for face in scene.face_regions:
            if text.overlaps(face, pad=0.01):
                composition -= 22.0
                notes.append("Tekst bedekt gezicht")
        if text.overlaps(horizon, pad=0.0) and layout.text_anchor in {"left", "right"}:
            # mild — horizontal titles often sit near horizon
            composition -= 6.0
            notes.append("Tekst raakt horizon")
        if text.overlaps(focus, pad=0.0):
            composition -= 18.0
            notes.append("Tekst bedekt focuspunt")
        else:
            composition += 6.0

        # Logo vs subject
        logo_rect = _logo_rect(layout.logo_position, layout.logo_scale)
        brand = 75.0
        if style_dna:
            if layout.logo_position == style_dna.logo_position:
                brand += 12.0
            else:
                brand -= 8.0
                notes.append("Logo wijkt af van Style DNA")
            if abs(layout.logo_scale - style_dna.logo_scale) <= 0.03:
                brand += 6.0
            if layout.text_anchor == style_dna.negative_space or (
                layout.text_anchor == style_dna.text_position
            ):
                brand += 8.0
        if logo_rect.overlaps(subject, pad=0.02):
            brand -= 20.0
            notes.append("Logo over onderwerp")
        else:
            brand += 5.0

        readability = 70.0 + min(20.0, layout.line_break_score * 0.2)
        if layout.title_scale == "large":
            readability += 8.0
        elif layout.title_scale == "small":
            readability -= 6.0
        if layout.orientation == "vertical" and len(layout.lines) > 3:
            readability -= 10.0

        # Negative space match
        neg = 70.0
        target_neg = (style_dna.negative_space if style_dna else "") or scene.negative_space
        if layout.text_anchor == target_neg:
            neg += 18.0
        elif layout.text_anchor in {"top", "bottom"} and target_neg in {"left", "right"}:
            neg -= 8.0
            notes.append("Negatieve ruimte niet optimaal")
        else:
            neg -= 12.0
            notes.append("Negatieve ruimte incorrect")

        # Visual balance — text opposite subject
        balance = 72.0
        subject_cx = subject.x + subject.w / 2
        text_cx = text.x + text.w / 2
        if (subject_cx > 0.55 and text_cx < 0.45) or (subject_cx < 0.45 and text_cx > 0.55):
            balance += 14.0
        elif abs(subject_cx - text_cx) < 0.15:
            balance -= 16.0
            notes.append("Tekst en onderwerp te gecentreerd samen")

        # Story visibility — subject not crushed
        story_ok = subject.coverage() >= 0.12 and not text.overlaps(subject, pad=0.02)
        ctr = 68.0 + (10.0 if layout.title_scale == "large" else 0.0)
        if story_ok:
            ctr += 12.0
        else:
            ctr -= 15.0
            notes.append("Story minder zichtbaar")

        professional = (
            0.25 * composition
            + 0.2 * brand
            + 0.2 * readability
            + 0.15 * neg
            + 0.2 * balance
        )
        if not notes:
            notes.append("Schone hiërarchie zonder overlap")
            professional = min(100.0, professional + 6.0)

        scores = DesignScores(
            composition=_clamp(composition),
            brand_match=_clamp(brand),
            readability=_clamp(readability),
            ctr=_clamp(ctr),
            visual_balance=_clamp(balance),
            negative_space=_clamp(neg),
            professional_design=_clamp(professional),
            notes=notes[:6],
        )
        scores.recompute()
        return scores


def _logo_rect(position: str, scale: float) -> RectNorm:
    s = max(0.06, min(0.22, scale))
    m = 0.04
    pos = (position or "bottom_left").casefold()
    x = m if "left" in pos else 1.0 - m - s
    y = m if "top" in pos else 1.0 - m - s
    if "center" in pos and "left" not in pos and "right" not in pos:
        x = 0.5 - s / 2
    return RectNorm(x=x, y=y, w=s, h=s)


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)
