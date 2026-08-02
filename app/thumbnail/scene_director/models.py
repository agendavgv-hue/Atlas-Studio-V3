"""Scene Director domain models — story scenes, not stock objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCORE_AXES: tuple[str, ...] = (
    "curiosity",
    "ctr_potential",
    "visual_strength",
    "brand_match",
    "emotion",
    "story",
)


@dataclass
class SceneScores:
    curiosity: float = 0.0
    ctr_potential: float = 0.0
    visual_strength: float = 0.0
    brand_match: float = 0.0
    emotion: float = 0.0
    story: float = 0.0
    overall: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SceneScores:
        raw = dict(data or {})
        values = {k: float(raw.get(k) or 0.0) for k in SCORE_AXES}
        overall = float(raw.get("overall") or 0.0)
        if overall <= 0 and values:
            overall = round(sum(values.values()) / len(values), 2)
        return cls(**values, overall=overall)

    def recompute(self) -> float:
        vals = [getattr(self, k) for k in SCORE_AXES]
        self.overall = round(sum(vals) / max(1, len(vals)), 2)
        return self.overall


@dataclass
class SceneCandidate:
    """One possible thumbnail story-scene (never a lone object)."""

    id: int
    title: str
    story: str = ""
    emotion: str = "curiosity"
    main_subject: str = ""
    secondary_subject: str = ""
    background: str = ""
    foreground: str = ""
    lighting: str = ""
    weather: str = ""
    camera: str = "eye_level"
    lens: str = "35mm cinematic"
    depth: str = "layered foreground midground background"
    atmosphere: str = "cinematic documentary"
    negative_space: str = "left"
    color_palette: list[str] = field(default_factory=list)
    visual_focus: str = ""
    scores: SceneScores = field(default_factory=SceneScores)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "story": self.story,
            "emotion": self.emotion,
            "main_subject": self.main_subject,
            "secondary_subject": self.secondary_subject,
            "background": self.background,
            "foreground": self.foreground,
            "lighting": self.lighting,
            "weather": self.weather,
            "camera": self.camera,
            "lens": self.lens,
            "depth": self.depth,
            "atmosphere": self.atmosphere,
            "negative_space": self.negative_space,
            "color_palette": list(self.color_palette),
            "visual_focus": self.visual_focus,
            "Curiosity": self.scores.curiosity,
            "CTR Potential": self.scores.ctr_potential,
            "Visual Strength": self.scores.visual_strength,
            "Brand Match": self.scores.brand_match,
            "Emotion": self.scores.emotion,
            "Story": self.scores.story,
            "scores": self.scores.to_dict(),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, default_id: int = 1) -> SceneCandidate:
        raw = dict(data or {})
        scores_raw = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
        if not scores_raw:
            scores_raw = {
                "curiosity": raw.get("Curiosity") or raw.get("curiosity"),
                "ctr_potential": raw.get("CTR Potential") or raw.get("ctr_potential"),
                "visual_strength": raw.get("Visual Strength") or raw.get("visual_strength"),
                "brand_match": raw.get("Brand Match") or raw.get("brand_match"),
                "emotion": raw.get("Emotion Score") or raw.get("emotion_score"),
                "story": raw.get("Story Score") or raw.get("story_score"),
            }
        return cls(
            id=int(raw.get("id") or default_id),
            title=str(raw.get("title") or f"Scene {default_id}").strip(),
            story=str(raw.get("story") or "").strip(),
            emotion=str(raw.get("emotion") or "curiosity").strip() or "curiosity",
            main_subject=str(raw.get("main_subject") or "").strip(),
            secondary_subject=str(raw.get("secondary_subject") or "").strip(),
            background=str(raw.get("background") or "").strip(),
            foreground=str(raw.get("foreground") or "").strip(),
            lighting=str(raw.get("lighting") or "").strip(),
            weather=str(raw.get("weather") or "").strip(),
            camera=str(raw.get("camera") or "eye_level").strip(),
            lens=str(raw.get("lens") or "35mm cinematic").strip(),
            depth=str(raw.get("depth") or "layered depth").strip(),
            atmosphere=str(raw.get("atmosphere") or "cinematic").strip(),
            negative_space=str(raw.get("negative_space") or "left").strip(),
            color_palette=[str(c) for c in (raw.get("color_palette") or [])][:6],
            visual_focus=str(raw.get("visual_focus") or "").strip(),
            scores=SceneScores.from_dict(scores_raw),
            notes=[str(n) for n in (raw.get("notes") or [])],
        )


@dataclass
class SceneBlueprint:
    """Locked scene for Prompt Builder — storytelling composition only."""

    main_subject: str = ""
    secondary_subject: str = ""
    background: str = ""
    foreground: str = ""
    lighting: str = "golden cinematic"
    weather: str = ""
    composition: str = "rule_of_thirds"
    negative_space: str = "left"
    emotion: str = "curiosity"
    story: str = ""
    camera: str = "eye_level"
    lens: str = "35mm cinematic"
    depth: str = "clear foreground midground background"
    atmosphere: str = "premium documentary"
    color_palette: list[str] = field(default_factory=list)
    visual_focus: str = ""
    title: str = ""
    selected_scene_id: int = 1
    selection_reason: str = ""
    candidates: list[SceneCandidate] = field(default_factory=list)
    channel_name: str = ""
    project_topic: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "Main Subject": self.main_subject,
            "Secondary Subject": self.secondary_subject,
            "Background": self.background,
            "Foreground": self.foreground,
            "Lighting": self.lighting,
            "Weather": self.weather,
            "Composition": self.composition,
            "Negative Space": self.negative_space,
            "Emotion": self.emotion,
            "Story": self.story,
            "Camera": self.camera,
            "Lens": self.lens,
            "Depth": self.depth,
            "Atmosphere": self.atmosphere,
            "Color Palette": list(self.color_palette),
            "Visual Focus": self.visual_focus,
            "Title": self.title,
            "selected_scene_id": self.selected_scene_id,
            "selection_reason": self.selection_reason,
            "why_this_scene": self.selection_reason,
            "candidates": [c.to_dict() for c in self.candidates],
            "channel_name": self.channel_name,
            "project_topic": self.project_topic,
            "extras": dict(self.extras),
            # machine keys
            "main_subject": self.main_subject,
            "secondary_subject": self.secondary_subject,
            "background": self.background,
            "foreground": self.foreground,
            "lighting": self.lighting,
            "weather": self.weather,
            "composition": self.composition,
            "negative_space": self.negative_space,
            "emotion": self.emotion,
            "story": self.story,
        }

    def prompt_block(self) -> str:
        colors = ", ".join(self.color_palette) or "channel brand palette"
        return (
            "SCENE BLUEPRINT (tell this exact story — never a lone object):\n"
            f"- Story: {self.story}\n"
            f"- Main subject (person/vehicle): {self.main_subject}\n"
            f"- Mysterious object: {self.secondary_subject}\n"
            f"- Epic background: {self.background}\n"
            f"- Foreground: {self.foreground or 'storytelling prop in near field'}\n"
            f"- Lighting: {self.lighting}\n"
            f"- Weather: {self.weather or 'atmospheric'}\n"
            f"- Composition: {self.composition}; negative space {self.negative_space} for title\n"
            f"- Camera / lens: {self.camera}, {self.lens}\n"
            f"- Depth: {self.depth}\n"
            f"- Atmosphere: {self.atmosphere}\n"
            f"- Emotion: {self.emotion}\n"
            f"- Visual focus: {self.visual_focus or self.main_subject}\n"
            f"- Color palette: {colors}\n"
            "MINIMUM RULES: one person OR vehicle + one mysterious object + "
            "one epic background + clear emotion + open space for title text. "
            "Do NOT generate a still-life of a single object."
        )

    def meets_minimum_rules(self) -> bool:
        has_actor = bool(self.main_subject.strip())
        has_mystery = bool(self.secondary_subject.strip())
        has_bg = bool(self.background.strip())
        has_emotion = bool(self.emotion.strip())
        has_story = len(self.story.split()) >= 8
        return has_actor and has_mystery and has_bg and has_emotion and has_story
