"""Score candidate thumbnail scenes for CTR storytelling."""

from __future__ import annotations

from app.creative.engine.brief import CreativeBrief
from app.creative.engine.style_profile import StyleProfile
from app.thumbnail.scene_director.models import SceneCandidate, SceneScores

_STORY_WORDS = {
    "discovers",
    "realizes",
    "vanishes",
    "disappears",
    "impossible",
    "hidden",
    "secret",
    "toward",
    "while",
    "as",
    "before",
    "after",
    "reveals",
    "approaches",
}
_LONE_OBJECT_BANS = {
    "compass on",
    "ship on sea",
    "map on table",
    "temple alone",
    "just a",
    "only a",
}


class SceneScorer:
    def score(
        self,
        scene: SceneCandidate,
        *,
        brief: CreativeBrief,
        thumbnail_profile: StyleProfile | None = None,
    ) -> SceneScores:
        blob = " ".join(
            [
                scene.title,
                scene.story,
                scene.main_subject,
                scene.secondary_subject,
                scene.background,
                scene.foreground,
                scene.emotion,
            ]
        ).casefold()

        curiosity = 55.0
        ctr = 55.0
        visual = 55.0
        brand = 55.0
        emotion_score = 55.0
        story = 50.0

        story_hits = sum(1 for w in _STORY_WORDS if w in blob)
        story += min(30.0, story_hits * 5.0)
        if len(scene.story.split()) >= 12:
            story += 12.0
            curiosity += 10.0
            ctr += 10.0
        if scene.main_subject and scene.secondary_subject and scene.background:
            visual += 18.0
            ctr += 12.0
            story += 10.0
        else:
            visual -= 20.0
            story -= 15.0
            ctr -= 15.0

        for ban in _LONE_OBJECT_BANS:
            if ban in blob and "while" not in blob and "as" not in blob:
                story -= 25.0
                ctr -= 20.0

        if any(k in blob for k in ("mystery", "impossible", "vanish", "hidden", "secret")):
            curiosity += 15.0
        if scene.emotion:
            emotion_score += 12.0
        for trait, value in (brief.personality.traits or {}).items():
            if value >= 70 and trait.casefold() in blob:
                brand += 6.0
                emotion_score += 3.0

        if thumbnail_profile is not None:
            if thumbnail_profile.mood and thumbnail_profile.mood.casefold() in blob:
                brand += 8.0
            if thumbnail_profile.negative_space == scene.negative_space:
                visual += 6.0
            if thumbnail_profile.reference_count > 0:
                brand += 5.0

        if scene.lighting:
            visual += 6.0
        if scene.weather:
            curiosity += 4.0
            visual += 4.0

        # Channel storytelling DNA
        story += float(getattr(brief.story, "mystery", 70) or 70) * 0.05
        curiosity += float(getattr(brief.story, "wonder", 70) or 70) * 0.04

        scores = SceneScores(
            curiosity=_clamp(curiosity),
            ctr_potential=_clamp(ctr),
            visual_strength=_clamp(visual),
            brand_match=_clamp(brand),
            emotion=_clamp(emotion_score),
            story=_clamp(story),
        )
        scores.recompute()
        return scores


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)
