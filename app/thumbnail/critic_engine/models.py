"""Thumbnail Critic domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CRITIC_AXES: tuple[str, ...] = (
    "storytelling",
    "curiosity",
    "mystery",
    "ctr_potential",
    "brand_consistency",
    "composition",
    "negative_space",
    "subject_visibility",
    "lighting",
    "contrast",
    "color_harmony",
    "visual_focus",
    "text_layout",
    "headline_size",
    "headline_hierarchy",
    "logo_position",
    "logo_size",
    "reference_similarity",
    "emotion",
    "professional_appearance",
    "overall_impact",
)

AXIS_LABELS: dict[str, str] = {
    "storytelling": "Storytelling",
    "curiosity": "Curiosity",
    "mystery": "Mystery",
    "ctr_potential": "CTR Potential",
    "brand_consistency": "Brand Consistency",
    "composition": "Composition",
    "negative_space": "Negative Space",
    "subject_visibility": "Subject Visibility",
    "lighting": "Lighting",
    "contrast": "Contrast",
    "color_harmony": "Color Harmony",
    "visual_focus": "Visual Focus",
    "text_layout": "Text Layout",
    "headline_size": "Headline Size",
    "headline_hierarchy": "Headline Hierarchy",
    "logo_position": "Logo Position",
    "logo_size": "Logo Size",
    "reference_similarity": "Reference Similarity",
    "emotion": "Emotion",
    "professional_appearance": "Professional Appearance",
    "overall_impact": "Overall Impact",
}

GROUP_AXES: dict[str, tuple[str, ...]] = {
    "story": ("storytelling", "curiosity", "mystery", "emotion"),
    "brand": ("brand_consistency", "logo_position", "logo_size", "reference_similarity"),
    "layout": ("text_layout", "headline_size", "headline_hierarchy", "negative_space"),
    "composition": ("composition", "subject_visibility", "visual_focus"),
    "ctr": ("ctr_potential", "overall_impact", "professional_appearance"),
    "visual": ("lighting", "contrast", "color_harmony"),
}


@dataclass
class AxisCritique:
    axis: str
    score: float = 0.0
    why: str = ""
    improvement: str = ""

    @property
    def label(self) -> str:
        return AXIS_LABELS.get(self.axis, self.axis.replace("_", " ").title())

    def to_dict(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "label": self.label,
            "score": round(self.score, 2),
            "Score": round(self.score, 2),
            "why": self.why,
            "Waarom": self.why,
            "improvement": self.improvement,
            "Verbetering": self.improvement,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AxisCritique:
        raw = dict(data or {})
        return cls(
            axis=str(raw.get("axis") or ""),
            score=float(raw.get("score") or raw.get("Score") or 0.0),
            why=str(raw.get("why") or raw.get("Waarom") or ""),
            improvement=str(raw.get("improvement") or raw.get("Verbetering") or ""),
        )


@dataclass
class CriticGroupScores:
    story: float = 0.0
    brand: float = 0.0
    layout: float = 0.0
    composition: float = 0.0
    ctr: float = 0.0
    curiosity: float = 0.0
    overall: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "Story": round(self.story, 2),
            "Brand": round(self.brand, 2),
            "Layout": round(self.layout, 2),
            "Composition": round(self.composition, 2),
            "CTR": round(self.ctr, 2),
            "Curiosity": round(self.curiosity, 2),
            "Overall": round(self.overall, 2),
            "story": round(self.story, 2),
            "brand": round(self.brand, 2),
            "layout": round(self.layout, 2),
            "composition": round(self.composition, 2),
            "ctr": round(self.ctr, 2),
            "curiosity": round(self.curiosity, 2),
            "overall": round(self.overall, 2),
        }


@dataclass
class CriticReport:
    axes: list[AxisCritique] = field(default_factory=list)
    groups: CriticGroupScores = field(default_factory=CriticGroupScores)
    overall: float = 0.0
    approved: bool = False
    threshold: int = 90
    attempt: int = 1
    channel_name: str = ""
    notes: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def axis_map(self) -> dict[str, AxisCritique]:
        return {a.axis: a for a in self.axes}

    def weak_axes(self, *, below: float | None = None) -> list[AxisCritique]:
        limit = float(below if below is not None else self.threshold)
        return sorted(
            [a for a in self.axes if a.score < limit],
            key=lambda a: a.score,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": round(self.overall, 2),
            "Overall": round(self.overall, 2),
            "approved": self.approved,
            "threshold": self.threshold,
            "attempt": self.attempt,
            "channel_name": self.channel_name,
            "groups": self.groups.to_dict(),
            "axes": [a.to_dict() for a in self.axes],
            "notes": list(self.notes),
            "extras": dict(self.extras),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CriticReport:
        raw = dict(data or {})
        axes = [
            AxisCritique.from_dict(item)
            for item in (raw.get("axes") or [])
            if isinstance(item, dict)
        ]
        groups_raw = raw.get("groups") if isinstance(raw.get("groups"), dict) else {}
        groups = CriticGroupScores(
            story=float(groups_raw.get("story") or groups_raw.get("Story") or 0),
            brand=float(groups_raw.get("brand") or groups_raw.get("Brand") or 0),
            layout=float(groups_raw.get("layout") or groups_raw.get("Layout") or 0),
            composition=float(
                groups_raw.get("composition") or groups_raw.get("Composition") or 0
            ),
            ctr=float(groups_raw.get("ctr") or groups_raw.get("CTR") or 0),
            curiosity=float(
                groups_raw.get("curiosity") or groups_raw.get("Curiosity") or 0
            ),
            overall=float(groups_raw.get("overall") or groups_raw.get("Overall") or 0),
        )
        return cls(
            axes=axes,
            groups=groups,
            overall=float(raw.get("overall") or raw.get("Overall") or groups.overall),
            approved=bool(raw.get("approved")),
            threshold=int(raw.get("threshold") or 90),
            attempt=int(raw.get("attempt") or 1),
            channel_name=str(raw.get("channel_name") or ""),
            notes=[str(n) for n in (raw.get("notes") or [])],
            extras=dict(raw.get("extras") or {}),
        )


@dataclass
class ImproveAction:
    axis: str
    action: str
    detail: str = ""
    target: str = "prompt"  # prompt | compose | plan

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ImproveAction:
        raw = dict(data or {})
        return cls(
            axis=str(raw.get("axis") or ""),
            action=str(raw.get("action") or ""),
            detail=str(raw.get("detail") or ""),
            target=str(raw.get("target") or "prompt"),
        )


@dataclass
class ImprovePlan:
    actions: list[ImproveAction] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    critic_overall: float = 0.0
    attempt: int = 1

    def prompt_block(self) -> str:
        if not self.summary_lines:
            return ""
        bullets = "\n".join(f"- {line}" for line in self.summary_lines)
        return (
            "IMPROVE PLAN (apply only these fixes — do not change strong axes):\n"
            f"{bullets}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions": [a.to_dict() for a in self.actions],
            "summary_lines": list(self.summary_lines),
            "critic_overall": self.critic_overall,
            "attempt": self.attempt,
            "Improve Plan": list(self.summary_lines),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ImprovePlan:
        raw = dict(data or {})
        return cls(
            actions=[
                ImproveAction.from_dict(item)
                for item in (raw.get("actions") or [])
                if isinstance(item, dict)
            ],
            summary_lines=[str(x) for x in (raw.get("summary_lines") or raw.get("Improve Plan") or [])],
            critic_overall=float(raw.get("critic_overall") or 0),
            attempt=int(raw.get("attempt") or 1),
        )


@dataclass
class ReviewVersion:
    attempt: int
    overall: float
    approved: bool
    image_relpath: str = ""
    report: CriticReport | None = None
    improve_plan: ImprovePlan | None = None
    prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "overall": round(self.overall, 2),
            "Score": round(self.overall, 2),
            "approved": self.approved,
            "image_relpath": self.image_relpath,
            "report": self.report.to_dict() if self.report else {},
            "improve_plan": self.improve_plan.to_dict() if self.improve_plan else {},
            "prompt": self.prompt,
        }


@dataclass
class ThumbnailReviewBoard:
    channel_name: str = ""
    project_name: str = ""
    winner_attempt: int = 1
    winner_score: float = 0.0
    versions: list[ReviewVersion] = field(default_factory=list)
    groups: CriticGroupScores = field(default_factory=CriticGroupScores)
    threshold: int = 90

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "project_name": self.project_name,
            "winner_attempt": self.winner_attempt,
            "winner_score": round(self.winner_score, 2),
            "Winnaar": self.winner_attempt,
            "threshold": self.threshold,
            "groups": self.groups.to_dict(),
            "versions": [v.to_dict() for v in self.versions],
            "Thumbnail 1": _version_summary(self.versions, 1),
            "Thumbnail 2": _version_summary(self.versions, 2),
            "Thumbnail 3": _version_summary(self.versions, 3),
        }


def _version_summary(versions: list[ReviewVersion], attempt: int) -> dict[str, Any]:
    for version in versions:
        if version.attempt == attempt:
            return {"Score": round(version.overall, 2), "approved": version.approved}
    return {"Score": None, "approved": False}
