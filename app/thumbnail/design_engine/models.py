"""Design Engine domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RectNorm:
    """Normalized rectangle (0–1)."""

    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    def overlaps(self, other: RectNorm, *, pad: float = 0.0) -> bool:
        return not (
            self.x + self.w + pad <= other.x
            or other.x + other.w + pad <= self.x
            or self.y + self.h + pad <= other.y
            or other.y + other.h + pad <= self.y
        )

    def coverage(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)


@dataclass
class SceneMap:
    """Vision analysis of the AI illustration only."""

    subject: RectNorm = field(default_factory=RectNorm)
    focus_x: float = 0.65
    focus_y: float = 0.45
    horizon_y: float = 0.42
    sky_ratio: float = 0.35
    water_ratio: float = 0.0
    dark_side: str = "left"
    light_side: str = "right"
    negative_space: str = "left"
    gaze_direction: str = "left"
    face_regions: list[RectNorm] = field(default_factory=list)
    object_regions: list[RectNorm] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject.to_dict(),
            "focus_x": self.focus_x,
            "focus_y": self.focus_y,
            "horizon_y": self.horizon_y,
            "sky_ratio": self.sky_ratio,
            "water_ratio": self.water_ratio,
            "dark_side": self.dark_side,
            "light_side": self.light_side,
            "negative_space": self.negative_space,
            "gaze_direction": self.gaze_direction,
            "face_regions": [r.to_dict() for r in self.face_regions],
            "object_regions": [r.to_dict() for r in self.object_regions],
            "notes": list(self.notes),
        }


@dataclass
class DesignScores:
    composition: float = 0.0
    brand_match: float = 0.0
    readability: float = 0.0
    ctr: float = 0.0
    visual_balance: float = 0.0
    negative_space: float = 0.0
    professional_design: float = 0.0
    overall: float = 0.0
    notes: list[str] = field(default_factory=list)

    def recompute(self) -> float:
        vals = [
            self.composition,
            self.brand_match,
            self.readability,
            self.ctr,
            self.visual_balance,
            self.negative_space,
            self.professional_design,
        ]
        self.overall = round(sum(vals) / max(1, len(vals)), 2)
        return self.overall

    def to_dict(self) -> dict[str, Any]:
        return {
            "Composition": round(self.composition, 2),
            "Brand Match": round(self.brand_match, 2),
            "Readability": round(self.readability, 2),
            "CTR": round(self.ctr, 2),
            "Visual Balance": round(self.visual_balance, 2),
            "Negative Space": round(self.negative_space, 2),
            "Professional Design": round(self.professional_design, 2),
            "Overall": round(self.overall, 2),
            **{k: round(getattr(self, k), 2) for k in (
                "composition",
                "brand_match",
                "readability",
                "ctr",
                "visual_balance",
                "negative_space",
                "professional_design",
                "overall",
            )},
            "notes": list(self.notes),
        }


@dataclass
class LayoutCandidate:
    """One full design layout proposal (not yet necessarily rendered)."""

    id: str
    label: str
    text_anchor: str = "left"  # left|right|top|bottom|center
    text_align: str = "left"
    max_lines: int = 3
    title_scale: str = "large"  # small|medium|large
    orientation: str = "horizontal"  # horizontal|vertical
    logo_position: str = "bottom_left"
    logo_scale: float = 0.11
    top_ratio: float = 0.12
    max_width_ratio: float = 0.40
    margin_x_ratio: float = 0.05
    lines: list[str] = field(default_factory=list)
    line_break_score: float = 0.0
    text_rect: RectNorm = field(default_factory=RectNorm)
    scores: DesignScores = field(default_factory=DesignScores)
    image_relpath: str = ""
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "text_anchor": self.text_anchor,
            "text_align": self.text_align,
            "max_lines": self.max_lines,
            "title_scale": self.title_scale,
            "orientation": self.orientation,
            "logo_position": self.logo_position,
            "logo_scale": self.logo_scale,
            "top_ratio": self.top_ratio,
            "max_width_ratio": self.max_width_ratio,
            "margin_x_ratio": self.margin_x_ratio,
            "lines": list(self.lines),
            "line_break_score": self.line_break_score,
            "text_rect": self.text_rect.to_dict(),
            "scores": self.scores.to_dict(),
            "Score": round(self.scores.overall, 2),
            "image_relpath": self.image_relpath,
            "why": self.why,
        }


@dataclass
class DesignReviewBoard:
    channel_name: str = ""
    project_name: str = ""
    winner_id: str = ""
    winner_score: float = 0.0
    winner_why: str = ""
    scene_map: dict[str, Any] = field(default_factory=dict)
    layouts: list[LayoutCandidate] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ranked = sorted(self.layouts, key=lambda L: L.scores.overall, reverse=True)
        preview = {
            f"Layout {L.id}": round(L.scores.overall, 2) for L in ranked[:12]
        }
        return {
            "channel_name": self.channel_name,
            "project_name": self.project_name,
            "winner_id": self.winner_id,
            "winner_score": round(self.winner_score, 2),
            "Winnaar": self.winner_id,
            "winner_why": self.winner_why,
            "Waarom": self.winner_why,
            "scene_map": dict(self.scene_map),
            "layouts": [L.to_dict() for L in self.layouts],
            "ranked_preview": preview,
            "extras": dict(self.extras),
            **preview,
        }
