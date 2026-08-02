"""Creative Director analysis — think before any image prompt."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CreativeDirectorAnalysis:
    """Structured reasoning output from the Creative Director LLM."""

    greatest_mystery: str = ""
    most_exciting_scene: str = ""
    highest_ctr_image: str = ""
    emotion: str = "curiosity"
    must_show_objects: list[str] = field(default_factory=list)
    must_hide_objects: list[str] = field(default_factory=list)
    negative_space: str = "left"
    title_placement: str = "left third"
    logo_placement: str = "bottom_left"
    dominant_colors: list[str] = field(default_factory=list)
    composition: str = "rule_of_thirds"
    camera_angle: str = "eye_level"
    lighting: str = "cinematic rim light"
    rationale: str = ""
    provider_id: str = ""
    model: str = ""
    used_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CreativeDirectorAnalysis:
        raw = dict(data or {})
        return cls(
            greatest_mystery=str(raw.get("greatest_mystery") or ""),
            most_exciting_scene=str(raw.get("most_exciting_scene") or ""),
            highest_ctr_image=str(raw.get("highest_ctr_image") or ""),
            emotion=str(raw.get("emotion") or "curiosity"),
            must_show_objects=[str(x) for x in (raw.get("must_show_objects") or [])][:12],
            must_hide_objects=[str(x) for x in (raw.get("must_hide_objects") or [])][:12],
            negative_space=str(raw.get("negative_space") or "left"),
            title_placement=str(raw.get("title_placement") or "left third"),
            logo_placement=str(raw.get("logo_placement") or "bottom_left"),
            dominant_colors=[str(x) for x in (raw.get("dominant_colors") or [])][:6],
            composition=str(raw.get("composition") or "rule_of_thirds"),
            camera_angle=str(raw.get("camera_angle") or "eye_level"),
            lighting=str(raw.get("lighting") or "cinematic rim light"),
            rationale=str(raw.get("rationale") or ""),
            provider_id=str(raw.get("provider_id") or ""),
            model=str(raw.get("model") or ""),
            used_fallback=bool(raw.get("used_fallback")),
        )

    def prompt_block(self) -> str:
        show = ", ".join(self.must_show_objects) or "one dominant subject"
        hide = ", ".join(self.must_hide_objects) or "text, logos, clutter"
        colors = ", ".join(self.dominant_colors) or "channel brand colors"
        return (
            "CREATIVE DIRECTOR ANALYSIS\n"
            f"- Greatest mystery: {self.greatest_mystery}\n"
            f"- Most exciting scene: {self.most_exciting_scene}\n"
            f"- Highest CTR image idea: {self.highest_ctr_image}\n"
            f"- Emotion: {self.emotion}\n"
            f"- Must show: {show}\n"
            f"- Must NOT show: {hide}\n"
            f"- Negative space: {self.negative_space}\n"
            f"- Title area: {self.title_placement}\n"
            f"- Logo area: {self.logo_placement}\n"
            f"- Dominant colors: {colors}\n"
            f"- Composition: {self.composition}\n"
            f"- Camera: {self.camera_angle}\n"
            f"- Lighting: {self.lighting}\n"
            f"- Why: {self.rationale}"
        )
