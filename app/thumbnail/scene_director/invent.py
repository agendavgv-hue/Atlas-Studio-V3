"""Invent possible thumbnail story-scenes from script + Creative Director."""

from __future__ import annotations

from app.creative.director.analysis import CreativeDirectorAnalysis
from app.creative.engine.brief import CreativeBrief
from app.creative.engine.style_profile import StyleProfile
from app.providers.base import TextProvider
from app.providers.errors import ProviderError
from app.thumbnail.concepts.models import ThumbnailConceptIdea
from app.thumbnail.scene_director.models import SceneCandidate
from app.thumbnail.text_utils import parse_json_object

MIN_SCENES = 5

_SYSTEM = (
    "You are Atlas Studio's Scene Director for YouTube thumbnails. "
    "You do NOT write image prompts. You invent story-scenes that maximize curiosity. "
    "Never propose a lone object on a table. Every scene needs a person OR vehicle, "
    "a mysterious object, an epic background, emotion, and space for title text."
)

_USER = """Channel: {channel}
Topic: {topic}

Channel personality (high traits): {personality}
Creative Director notes:
{director}

Reference style: {references}

Script:
---
{script}
---

Sheet (optional):
---
{sheet}
---

Invent at least {min_scenes} DISTINCT possible thumbnail SCENES.
Search the script for mystery, revelation, danger, conflict, unanswered questions —
NOT pretty stock images.

Return ONLY JSON:
{{
  "scenes": [
    {{
      "id": 1,
      "title": "short curiosity title",
      "story": "one dense sentence telling the thumbnail story with action",
      "emotion": "curiosity|mystery|wonder|fear|adventure|epic",
      "main_subject": "person or vehicle",
      "secondary_subject": "mysterious object",
      "background": "epic environment",
      "foreground": "near-field storytelling element",
      "lighting": "...",
      "weather": "...",
      "camera": "eye_level|low_angle|high_angle",
      "lens": "35mm|50mm|85mm cinematic",
      "depth": "...",
      "atmosphere": "...",
      "negative_space": "left|right",
      "color_palette": ["#112233"],
      "visual_focus": "where the eye lands first"
    }}
  ]
}}
"""


class SceneInventor:
    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self._text = text_provider

    def invent(
        self,
        *,
        brief: CreativeBrief,
        script_text: str = "",
        sheet_text: str = "",
        topic: str = "",
        analysis: CreativeDirectorAnalysis | None = None,
        best_concept: ThumbnailConceptIdea | None = None,
        thumbnail_profile: StyleProfile | None = None,
        min_scenes: int = MIN_SCENES,
    ) -> list[SceneCandidate]:
        topic_text = (
            topic or brief.project.topic or brief.project.idea or brief.channel_name
        ).strip()
        try:
            if self._text is not None and (script_text or topic_text).strip():
                scenes = self._invent_ai(
                    brief=brief,
                    script_text=script_text,
                    sheet_text=sheet_text,
                    topic=topic_text,
                    analysis=analysis,
                    thumbnail_profile=thumbnail_profile,
                    min_scenes=min_scenes,
                )
                if len(scenes) >= min_scenes:
                    return scenes
        except (ProviderError, Exception):  # noqa: BLE001
            pass
        return self._invent_heuristic(
            brief=brief,
            script_text=script_text,
            topic=topic_text,
            analysis=analysis,
            best_concept=best_concept,
            thumbnail_profile=thumbnail_profile,
            min_scenes=min_scenes,
        )

    def _invent_ai(
        self,
        *,
        brief: CreativeBrief,
        script_text: str,
        sheet_text: str,
        topic: str,
        analysis: CreativeDirectorAnalysis | None,
        thumbnail_profile: StyleProfile | None,
        min_scenes: int,
    ) -> list[SceneCandidate]:
        assert self._text is not None
        traits = [
            f"{k}:{v:.0f}"
            for k, v in sorted(
                (brief.personality.traits or {}).items(), key=lambda kv: -kv[1]
            )
            if v >= 65
        ][:8]
        director = analysis.prompt_block() if analysis else "No prior director analysis."
        refs = "none"
        if thumbnail_profile is not None:
            refs = (
                f"neg={thumbnail_profile.negative_space}; mood={thumbnail_profile.mood}; "
                f"contrast={thumbnail_profile.contrast}"
            )
        prompt = _USER.format(
            channel=brief.channel_name,
            topic=topic,
            personality=", ".join(traits) or "documentary",
            director=director,
            references=refs,
            script=(script_text or topic)[:10000],
            sheet=(sheet_text or "")[:4000],
            min_scenes=max(MIN_SCENES, min_scenes),
        )
        raw = self._text.generate_text(prompt, system=_SYSTEM)
        data = parse_json_object(raw, label="Scene Director")
        scenes = _parse_scenes(data.get("scenes"), min_count=min_scenes)
        if len(scenes) < min_scenes:
            scenes.extend(
                self._invent_heuristic(
                    brief=brief,
                    script_text=script_text,
                    topic=topic,
                    analysis=analysis,
                    best_concept=None,
                    thumbnail_profile=thumbnail_profile,
                    min_scenes=min_scenes,
                )[len(scenes) :]
            )
        return scenes[: max(min_scenes, len(scenes))]

    def _invent_heuristic(
        self,
        *,
        brief: CreativeBrief,
        script_text: str,
        topic: str,
        analysis: CreativeDirectorAnalysis | None,
        best_concept: ThumbnailConceptIdea | None,
        thumbnail_profile: StyleProfile | None,
        min_scenes: int,
    ) -> list[SceneCandidate]:
        actor = "explorer"
        mystery = brief.project.primary_subject or _keyword(topic) or "ancient artifact"
        place = brief.project.primary_location or "storm-lit horizon"
        if analysis is not None:
            if analysis.must_show_objects:
                mystery = analysis.must_show_objects[0]
            if analysis.most_exciting_scene:
                place = analysis.most_exciting_scene
            actor = "silhouette of an explorer" if "person" not in mystery.casefold() else actor
        if best_concept is not None:
            if best_concept.hero_subject:
                mystery = best_concept.hero_subject
            if best_concept.background:
                place = best_concept.background

        neg = "left"
        if thumbnail_profile and thumbnail_profile.negative_space not in {"", "auto"}:
            neg = thumbnail_profile.negative_space
        elif analysis and analysis.negative_space:
            neg = analysis.negative_space

        emotion = (
            (analysis.emotion if analysis else "")
            or brief.thumbnail.emotion
            or "curiosity"
        )
        palette = []
        if analysis and analysis.dominant_colors:
            palette = list(analysis.dominant_colors[:4])
        else:
            palette = [
                c
                for c in (
                    brief.brand.primary_color,
                    brief.brand.secondary_color,
                    brief.brand.accent_color,
                )
                if c
            ]

        templates = [
            (
                "IMPOSSIBLE DIRECTION",
                f"{actor.capitalize()} realizes {mystery} points toward an impossible direction "
                f"while a mysterious ship disappears into fog over {place}.",
                actor,
                mystery,
                f"fogbound {place}",
                "old map in the foreground",
                "golden cinematic rim light",
                "heavy fog",
            ),
            (
                "TOO LATE TO TURN",
                f"A weathered vessel races toward a gigantic whirlpool as {mystery} "
                f"lies open in the foreground and lightning tears the sky.",
                "abandoned sailing ship",
                mystery,
                "gigantic whirlpool under storm sky",
                f"{mystery} in near field",
                "harsh lightning contrast",
                "violent storm",
            ),
            (
                "JUST REVEALED",
                f"From a cliff edge, {actor} looks down as a hidden temple emerges "
                f"between the mist, while {mystery} glows in their hands.",
                actor,
                mystery,
                "hidden temple appearing through mist",
                "cliff edge stones",
                "pale dawn breaking through fog",
                "thick mist",
            ),
            (
                "THE VANISHING",
                f"{actor.capitalize()} stands alone on deck as crew footprints end mid-plank "
                f"and {mystery} still spins while {place} swallows the horizon.",
                actor,
                mystery,
                place,
                "ending footprints on wet wood",
                "cold blue moonlight",
                "rolling fog",
            ),
            (
                "NOT NATURAL",
                f"{actor.capitalize()} measures {mystery} beside a structure that should not exist, "
                f"while an epic storm builds behind the impossible geometry of {place}.",
                actor,
                mystery,
                f"impossible geometry at {place}",
                "measurement tools and notes",
                "documentary key light with storm backlight",
                "approaching storm",
            ),
            (
                "FINAL WARNING",
                f"A rescue craft turns away as {mystery} flares with unnatural light "
                f"and the sea around {place} collapses inward.",
                "small rescue craft",
                mystery,
                f"collapsing sea around {place}",
                "spray and rope in foreground",
                "urgent red-gold emergency light",
                "chaotic spray",
            ),
        ]

        # Prefer script snippet for first story if rich enough.
        script_seed = " ".join((script_text or "").split()[:24])
        scenes: list[SceneCandidate] = []
        for i, tmpl in enumerate(templates[: max(min_scenes, MIN_SCENES)], start=1):
            title, story, main, secondary, background, foreground, lighting, weather = tmpl
            if i == 1 and len(script_seed.split()) >= 8:
                story = (
                    f"{story} Script seed: {script_seed}"
                )
            scenes.append(
                SceneCandidate(
                    id=i,
                    title=title,
                    story=story,
                    emotion=emotion,
                    main_subject=main,
                    secondary_subject=secondary,
                    background=background,
                    foreground=foreground,
                    lighting=lighting,
                    weather=weather,
                    camera="low_angle" if i in {2, 5} else "eye_level",
                    lens="35mm cinematic",
                    depth="strong foreground–midground–background separation",
                    atmosphere="premium documentary mystery",
                    negative_space=neg,
                    color_palette=list(palette),
                    visual_focus=f"{main} reacting to {secondary}",
                    notes=["heuristic scene from script/topic + Channel DNA"],
                )
            )
        return scenes


def _parse_scenes(raw: object, *, min_count: int) -> list[SceneCandidate]:
    items = raw if isinstance(raw, list) else []
    scenes: list[SceneCandidate] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        # Accept concept-shaped payloads as a soft fallback.
        if not item.get("main_subject") and item.get("hero_subject"):
            item = {
                **item,
                "main_subject": "explorer",
                "secondary_subject": item.get("hero_subject")
                or item.get("secondary_subject")
                or "mysterious artifact",
                "story": item.get("story")
                or item.get("idea")
                or (
                    f"explorer confronts {item.get('hero_subject')} "
                    f"against {item.get('background') or 'an epic horizon'}."
                ),
            }
        scene = SceneCandidate.from_dict(item, default_id=i)
        if not scene.main_subject:
            scene.main_subject = "explorer"
        if not scene.secondary_subject:
            scene.secondary_subject = "mysterious artifact"
        if not scene.background:
            scene.background = "epic storm horizon"
        if not scene.story:
            scene.story = (
                f"{scene.main_subject} confronts {scene.secondary_subject} "
                f"against {scene.background}."
            )
        scenes.append(scene)
    return scenes


def _keyword(text: str) -> str:
    words = [w.strip(".,:;!?\"'") for w in (text or "").split() if w.strip()]
    skip = {"the", "a", "an", "of", "and", "in", "on", "to", "for"}
    for word in words:
        if word.casefold() not in skip and len(word) > 2:
            return word
    return "artifact"
