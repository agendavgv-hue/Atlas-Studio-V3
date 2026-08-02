"""Thumbnail concept models — think before you generate."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCORE_AXES: tuple[str, ...] = (
    "curiosity",
    "mystery",
    "visual_impact",
    "ctr_potential",
    "originality",
    "storytelling",
    "brand_match",
    "emotion",
    "composition",
    "thumbnail_strength",
)


@dataclass
class ConceptScores:
    curiosity: float = 0.0
    mystery: float = 0.0
    visual_impact: float = 0.0
    ctr_potential: float = 0.0
    originality: float = 0.0
    storytelling: float = 0.0
    brand_match: float = 0.0
    emotion: float = 0.0
    composition: float = 0.0
    thumbnail_strength: float = 0.0
    overall: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ConceptScores:
        raw = dict(data or {})
        values = {axis: float(raw.get(axis) or 0.0) for axis in SCORE_AXES}
        overall = float(raw.get("overall") or 0.0)
        if overall <= 0 and values:
            overall = round(sum(values.values()) / len(values), 2)
        return cls(**values, overall=overall)

    def recompute_overall(self) -> float:
        values = [getattr(self, axis) for axis in SCORE_AXES]
        self.overall = round(sum(values) / max(1, len(values)), 2)
        return self.overall


@dataclass
class ThumbnailConceptIdea:
    """One thumbnail concept — never an image prompt."""

    id: int
    title: str
    foreground: str = ""
    midground: str = ""
    background: str = ""
    lighting: str = ""
    emotion: str = "curiosity"
    elements: list[str] = field(default_factory=list)
    hero_subject: str = ""
    hook: str = ""
    idea: str = ""
    scores: ConceptScores = field(default_factory=ConceptScores)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "foreground": self.foreground,
            "midground": self.midground,
            "background": self.background,
            "lighting": self.lighting,
            "emotion": self.emotion,
            "elements": list(self.elements),
            "hero_subject": self.hero_subject,
            "hook": self.hook,
            "idea": self.idea or self.summary_line(),
            "scores": self.scores.to_dict(),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, default_id: int = 1) -> ThumbnailConceptIdea:
        raw = dict(data or {})
        elements = raw.get("elements") or []
        if not isinstance(elements, list):
            elements = []
        return cls(
            id=int(raw.get("id") or default_id),
            title=str(raw.get("title") or f"Concept {default_id}").strip(),
            foreground=str(raw.get("foreground") or "").strip(),
            midground=str(raw.get("midground") or "").strip(),
            background=str(raw.get("background") or "").strip(),
            lighting=str(raw.get("lighting") or "").strip(),
            emotion=str(raw.get("emotion") or "curiosity").strip() or "curiosity",
            elements=[str(e).strip() for e in elements if str(e).strip()][:12],
            hero_subject=str(raw.get("hero_subject") or "").strip(),
            hook=str(raw.get("hook") or "").strip(),
            idea=str(raw.get("idea") or "").strip(),
            scores=ConceptScores.from_dict(
                raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
            ),
            notes=[str(n) for n in (raw.get("notes") or [])],
        )

    def summary_line(self) -> str:
        if self.idea:
            return self.idea
        parts = [p for p in (self.foreground, self.midground, self.background) if p]
        if parts:
            return "; ".join(parts)
        return self.title

    def prompt_block(self) -> str:
        elements = ", ".join(self.elements) if self.elements else self.summary_line()
        return (
            "BEST THUMBNAIL CONCEPT (generate only this scene):\n"
            f"- Title / hook direction: {self.title}\n"
            f"- Hero subject: {self.hero_subject or self.foreground or self.title}\n"
            f"- Foreground: {self.foreground or 'dominant iconic object'}\n"
            f"- Midground: {self.midground or 'supporting narrative element'}\n"
            f"- Background: {self.background or 'atmospheric environment'}\n"
            f"- Lighting: {self.lighting or 'cinematic high-contrast light'}\n"
            f"- Emotion: {self.emotion}\n"
            f"- Elements: {elements}\n"
            f"- Curiosity hook text (Atlas will render later): {self.hook or self.title}"
        )


@dataclass
class ConceptBoard:
    """Full think→score→choose result for one project."""

    project_topic: str
    channel_name: str
    concepts: list[ThumbnailConceptIdea] = field(default_factory=list)
    selected_id: int = 1
    selected_reason: str = ""
    reference_analysis: dict[str, Any] = field(default_factory=dict)
    personality_focus: list[str] = field(default_factory=list)
    selected_scene: str = ""
    click_value_reason: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def chosen(self) -> ThumbnailConceptIdea:
        for concept in self.concepts:
            if concept.id == self.selected_id:
                return concept
        return self.concepts[0] if self.concepts else ThumbnailConceptIdea(id=1, title="Concept")

    def to_dict(self) -> dict[str, Any]:
        chosen = self.chosen
        return {
            "project_topic": self.project_topic,
            "channel_name": self.channel_name,
            "concepts": [c.to_dict() for c in self.concepts],
            "selected_id": self.selected_id,
            "selected_reason": self.selected_reason,
            "chosen_concept_id": self.selected_id,
            "chosen_reason": self.selected_reason,
            "winner": chosen.to_dict(),
            "elements_to_use": {
                "foreground": chosen.foreground,
                "midground": chosen.midground,
                "background": chosen.background,
                "lighting": chosen.lighting,
                "emotion": chosen.emotion,
                "hero_subject": chosen.hero_subject,
                "hook": chosen.hook or chosen.title,
                "elements": list(chosen.elements),
            },
            "reference_analysis": dict(self.reference_analysis),
            "personality_focus": list(self.personality_focus),
            "selected_scene": self.selected_scene,
            "click_value_reason": self.click_value_reason,
            "extras": dict(self.extras),
        }
