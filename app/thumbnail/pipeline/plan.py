"""Thumbnail Pipeline V3 — composition plan before any AI call."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.creative.engine.brief import CreativeBrief
from app.creative.engine.style_profile import StyleProfile
from app.thumbnail.concepts.models import ThumbnailConceptIdea
from app.thumbnail.scene_director.models import SceneBlueprint


@dataclass
class ThumbnailPlan:
    """Full composition blueprint — saved as thumbnail_plan.json."""

    main_subject: str = ""
    secondary_subject: str = ""
    background: str = ""
    foreground: str = ""
    emotion: str = "curiosity"
    lighting: str = "cinematic rim light"
    camera_angle: str = "eye_level"
    color_palette: list[str] = field(default_factory=list)
    negative_space: str = "left"
    text_area: str = "left third"
    logo_area: str = "bottom_left"
    story_focus: str = ""
    composition_style: str = "rule_of_thirds"
    rule_of_thirds: str = "subject on right third"
    focal_point: str = "main subject eyes or silhouette peak"
    leading_lines: str = "depth lines toward subject"
    depth: str = "strong foreground midground background separation"
    visual_hierarchy: str = "subject > negative space > background"
    hook: str = ""
    channel_name: str = ""
    reference_count: int = 0
    brand_strength: float = 85.0
    documentary_feel: float = 70.0
    realism: float = 85.0
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ThumbnailPlan:
        raw = dict(data or {})
        palette = raw.get("color_palette") or []
        if not isinstance(palette, list):
            palette = []
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        extras = dict(raw.get("extras") or {}) if isinstance(raw.get("extras"), dict) else {}
        for key, value in raw.items():
            if key not in known and key != "extras":
                extras[key] = value
        return cls(
            main_subject=str(raw.get("main_subject") or ""),
            secondary_subject=str(raw.get("secondary_subject") or ""),
            background=str(raw.get("background") or ""),
            foreground=str(raw.get("foreground") or ""),
            emotion=str(raw.get("emotion") or "curiosity"),
            lighting=str(raw.get("lighting") or "cinematic rim light"),
            camera_angle=str(raw.get("camera_angle") or "eye_level"),
            color_palette=[str(c) for c in palette][:6],
            negative_space=str(raw.get("negative_space") or "left"),
            text_area=str(raw.get("text_area") or "left third"),
            logo_area=str(raw.get("logo_area") or "bottom_left"),
            story_focus=str(raw.get("story_focus") or ""),
            composition_style=str(raw.get("composition_style") or "rule_of_thirds"),
            rule_of_thirds=str(raw.get("rule_of_thirds") or "subject on right third"),
            focal_point=str(raw.get("focal_point") or "main subject"),
            leading_lines=str(raw.get("leading_lines") or "depth lines toward subject"),
            depth=str(raw.get("depth") or "layered depth"),
            visual_hierarchy=str(
                raw.get("visual_hierarchy") or "subject > negative space > background"
            ),
            hook=str(raw.get("hook") or ""),
            channel_name=str(raw.get("channel_name") or ""),
            reference_count=int(raw.get("reference_count") or 0),
            brand_strength=float(raw.get("brand_strength") or 85.0),
            documentary_feel=float(raw.get("documentary_feel") or 70.0),
            realism=float(raw.get("realism") or 85.0),
            extras=extras,
        )

    def prompt_block(self) -> str:
        colors = ", ".join(self.color_palette) or "channel brand palette"
        return (
            "THUMBNAIL PLAN (follow exactly):\n"
            f"- Main subject: {self.main_subject}\n"
            f"- Secondary: {self.secondary_subject or 'none — keep single dominant subject'}\n"
            f"- Background: {self.background}\n"
            f"- Foreground: {self.foreground or 'subtle atmospheric depth only'}\n"
            f"- Emotion: {self.emotion}\n"
            f"- Lighting: {self.lighting}\n"
            f"- Camera: {self.camera_angle}\n"
            f"- Color palette: {colors}\n"
            f"- Negative space: {self.negative_space} ({self.text_area} reserved for title)\n"
            f"- Logo area reserved: {self.logo_area} (do not paint a logo)\n"
            f"- Story focus: {self.story_focus}\n"
            f"- Composition: {self.composition_style}; {self.rule_of_thirds}\n"
            f"- Focal point: {self.focal_point}\n"
            f"- Leading lines: {self.leading_lines}\n"
            f"- Depth: {self.depth}\n"
            f"- Visual hierarchy: {self.visual_hierarchy}\n"
            f"- Documentary feel {self.documentary_feel:.0f}/100; "
            f"realism {self.realism:.0f}/100; brand strength {self.brand_strength:.0f}/100"
        )


def save_thumbnail_plan(path: Path, plan: ThumbnailPlan) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def load_thumbnail_plan(path: Path) -> ThumbnailPlan | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return ThumbnailPlan.from_dict(raw)


class ThumbnailCompositionPlanner:
    """Build a full ThumbnailPlan from Creative Brief + analysis + style profile."""

    def plan(
        self,
        brief: CreativeBrief,
        *,
        hero_subject: str,
        hook: str,
        location: str = "",
        thumbnail_profile: StyleProfile | None = None,
        critic_feedback: str = "",
        best_concept: ThumbnailConceptIdea | None = None,
        scene_blueprint: SceneBlueprint | None = None,
    ) -> ThumbnailPlan:
        t = brief.thumbnail
        i = brief.image
        story = brief.story
        profile = thumbnail_profile
        concept = best_concept
        scene = scene_blueprint

        neg = (t.negative_space or "left").strip().casefold()
        if neg in {"", "auto"}:
            neg = ""
            if scene and scene.negative_space not in {"", "auto"}:
                neg = scene.negative_space
            elif profile and profile.negative_space not in {"", "auto"}:
                neg = profile.negative_space
            neg = neg or "left"
        subject_side = "right" if neg == "left" else "left" if neg == "right" else "right"
        if profile and profile.subject_bias and profile.subject_bias not in {"", "auto"}:
            subject_side = profile.subject_bias

        palette: list[str] = []
        if scene and scene.color_palette:
            palette.extend(scene.color_palette[:4])
        if profile and profile.dominant_colors:
            for color in profile.dominant_colors[:4]:
                if color not in palette:
                    palette.append(color)
        for color in (
            brief.brand.primary_color,
            brief.brand.secondary_color,
            brief.brand.accent_color,
        ):
            if color and color not in palette:
                palette.append(color)

        logo_area = t.logo_position if t.logo_position != "auto" else (
            profile.logo_bias if profile else "bottom_left"
        )
        if logo_area == "auto":
            logo_area = "bottom_left"

        lighting = (
            (scene.lighting if scene and scene.lighting else "")
            or (concept.lighting if concept and concept.lighting else "")
            or i.lighting
            or (profile.atmosphere if profile else "")
            or "cinematic rim light"
        )
        if profile and profile.brightness == "dark" and "low-key" not in lighting.casefold():
            lighting = f"low-key {lighting}, deep shadows, selective highlights"

        emotion = (
            (scene.emotion if scene and scene.emotion else "")
            or (concept.emotion if concept else "")
            or t.emotion
            or brief.project.primary_emotion
            or "curiosity"
        )
        if profile and profile.mood and profile.mood.casefold() not in emotion.casefold():
            emotion = f"{emotion}, {profile.mood}"

        loc = (location or brief.project.primary_location or "").strip()
        background = (
            (scene.background if scene and scene.background else "")
            or (concept.background if concept and concept.background else "")
            or loc
            or "atmospheric documentary environment matching channel identity"
        )
        foreground = (
            (scene.foreground if scene and scene.foreground else "")
            or (concept.foreground if concept and concept.foreground else "")
            or "subtle atmospheric particles or soft vignette depth"
        )
        if scene is not None:
            secondary = scene.secondary_subject
            hero = (
                scene.main_subject
                or hero_subject
                or brief.project.primary_subject
                or "explorer"
            ).strip()
            story_focus = scene.story or scene.title
            camera = scene.camera or i.camera_style or (
                profile.camera_angle if profile else "eye_level"
            )
            composition = scene.composition or t.composition_style or "rule_of_thirds"
            depth = scene.depth or "clear foreground–midground–background separation"
            focal = scene.visual_focus or f"{hero} reacting to {secondary}"
        else:
            secondary = (
                (concept.midground if concept and concept.midground else "")
                if (concept is not None or t.dominant_subject != "one")
                else ""
            )
            if t.dominant_subject == "one" and concept is None:
                secondary = ""
            hero = (
                (concept.hero_subject if concept and concept.hero_subject else "")
                or hero_subject
                or brief.project.primary_subject
                or "one dominant cinematic subject"
            ).strip()
            story_focus = (
                (concept.summary_line() if concept else "")
                or brief.project.idea
                or brief.project.topic
                or getattr(story, "storytelling_style", "")
                or hook
            )
            camera = i.camera_style or (profile.camera_angle if profile else "eye_level")
            composition = t.composition_style or "rule_of_thirds"
            depth = "clear foreground–midground–background separation"
            focal = "dominant subject silhouette / face / artifact peak"

        hook_text = (
            (concept.hook if concept and concept.hook else "")
            or (concept.title if concept else "")
            or (scene.title if scene else "")
            or hook
        ).strip()
        if not story_focus:
            story_focus = hook_text
        if critic_feedback:
            story_focus = f"{story_focus}. Adjust: {critic_feedback[:200]}"

        if composition in {"medium", "close", "wide"}:
            composition = {
                "medium": "medium shot rule of thirds",
                "close": "close cinematic portrait framing",
                "wide": "wide establishing cinematic frame",
            }.get(composition, composition)

        extras = {
            "image_atmosphere": getattr(i, "atmosphere", "")
            or (scene.atmosphere if scene else ""),
            "story_style": getattr(story, "storytelling_style", ""),
            "story_emotion": getattr(story, "emotion", ""),
            "critic_feedback": critic_feedback[:400] if critic_feedback else "",
            "weather": scene.weather if scene else "",
            "lens": scene.lens if scene else "",
        }
        if concept is not None:
            extras["best_concept_id"] = concept.id
            extras["best_concept_title"] = concept.title
            extras["best_concept_elements"] = list(concept.elements)
            extras["best_concept_score"] = concept.scores.overall
        if scene is not None:
            extras["scene_id"] = scene.selected_scene_id
            extras["scene_title"] = scene.title
            extras["selection_reason"] = scene.selection_reason
            extras["scene_candidate_count"] = len(scene.candidates)

        return ThumbnailPlan(
            main_subject=hero,
            secondary_subject=secondary,
            background=background,
            foreground=foreground,
            emotion=emotion,
            lighting=lighting,
            camera_angle=str(camera),
            color_palette=palette[:6],
            negative_space=neg,
            text_area=f"{neg} third clear for title",
            logo_area=str(logo_area),
            story_focus=str(story_focus),
            composition_style=str(composition),
            rule_of_thirds=f"subject on the {subject_side} third, open {neg} for text",
            focal_point=str(focal),
            leading_lines="environmental lines guide eye to subject",
            depth=str(depth),
            visual_hierarchy="hero subject first, mysterious object second, epic background third",
            hook=hook_text,
            channel_name=brief.channel_name,
            reference_count=profile.reference_count if profile else brief.reference_count,
            brand_strength=float(t.brand_strength or 85.0),
            documentary_feel=float(t.documentary or 70.0),
            realism=float(t.realism or i.realism or 85.0),
            extras=extras,
        )
