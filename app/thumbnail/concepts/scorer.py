"""Score thumbnail concepts against Channel DNA + reference style."""

from __future__ import annotations

from app.creative.engine.brief import CreativeBrief
from app.creative.engine.style_profile import StyleProfile
from app.thumbnail.concepts.models import ConceptScores, ThumbnailConceptIdea


_MYSTERY_WORDS = {
    "mystery",
    "fog",
    "mist",
    "shadow",
    "secret",
    "hidden",
    "ancient",
    "unknown",
    "vanish",
    "disappear",
    "dark",
    "storm",
}
_IMPACT_WORDS = {
    "giant",
    "gigantic",
    "massive",
    "epic",
    "lightning",
    "wave",
    "vortex",
    "whirlpool",
    "close-up",
    "dramatic",
    "silhouette",
}
_STORY_WORDS = {
    "explorer",
    "ship",
    "map",
    "lantern",
    "compass",
    "ruins",
    "island",
    "lighthouse",
    "traveler",
    "discover",
}


class ConceptScorer:
    """Heuristic CTR/brand scorer — generic for any trained channel."""

    def score(
        self,
        concept: ThumbnailConceptIdea,
        *,
        brief: CreativeBrief,
        thumbnail_profile: StyleProfile | None = None,
        sibling_ideas: list[str] | None = None,
    ) -> ConceptScores:
        blob = " ".join(
            [
                concept.title,
                concept.idea,
                concept.foreground,
                concept.midground,
                concept.background,
                concept.lighting,
                concept.emotion,
                " ".join(concept.elements),
                concept.hero_subject,
            ]
        ).casefold()

        personality = brief.personality.traits or {}
        top_traits = [
            k for k, v in sorted(personality.items(), key=lambda kv: -kv[1]) if v >= 70
        ][:8]

        curiosity = 62.0
        mystery = 58.0
        visual_impact = 60.0
        ctr = 60.0
        originality = 70.0
        storytelling = 60.0
        brand_match = 55.0
        emotion_score = 60.0
        composition = 65.0
        strength = 60.0

        # Curiosity / mystery keywords
        mystery_hits = sum(1 for w in _MYSTERY_WORDS if w in blob)
        curiosity += min(25.0, mystery_hits * 5.0)
        mystery += min(30.0, mystery_hits * 6.0)
        if "curiosity" in (concept.emotion or "").casefold():
            curiosity += 10.0
        if "mystery" in (concept.emotion or "").casefold():
            mystery += 12.0

        impact_hits = sum(1 for w in _IMPACT_WORDS if w in blob)
        visual_impact += min(28.0, impact_hits * 7.0)
        if concept.foreground and concept.background:
            visual_impact += 8.0
            composition += 8.0

        story_hits = sum(1 for w in _STORY_WORDS if w in blob)
        storytelling += min(25.0, story_hits * 5.0)
        if concept.midground:
            storytelling += 6.0

        # Single dominant subject preference (thumbnail strength)
        if concept.hero_subject or concept.foreground:
            strength += 12.0
            ctr += 8.0
        if len(concept.elements) <= 4:
            strength += 8.0
            composition += 6.0
        elif len(concept.elements) >= 7:
            strength -= 10.0
            composition -= 8.0

        # Emotion alignment with concept emotion + personality
        emotion_key = (concept.emotion or "").casefold()
        if emotion_key:
            emotion_score += 10.0
        for trait in top_traits:
            if trait.casefold() in blob or trait.casefold() in emotion_key:
                brand_match += 6.0
                emotion_score += 4.0
        brand_match += min(20.0, float(brief.thumbnail.brand_strength or 85) * 0.12)

        # Reference style alignment
        if thumbnail_profile is not None:
            if thumbnail_profile.mood and thumbnail_profile.mood.casefold() in blob:
                brand_match += 8.0
            if thumbnail_profile.atmosphere and thumbnail_profile.atmosphere.casefold() in blob:
                composition += 5.0
            if thumbnail_profile.brightness == "dark" and any(
                w in blob for w in ("dark", "storm", "night", "fog", "shadow")
            ):
                brand_match += 6.0
                visual_impact += 4.0
            if thumbnail_profile.reference_count > 0:
                brand_match += 5.0
                strength += 4.0

        # Story DNA
        story_emotion = (getattr(brief.story, "emotion", "") or "").casefold()
        if story_emotion and story_emotion in blob:
            storytelling += 8.0
        mystery += float(getattr(brief.story, "mystery", 70) or 70) * 0.08
        curiosity += float(getattr(brief.story, "wonder", 70) or 70) * 0.05

        # Originality vs siblings
        siblings = [s.casefold() for s in (sibling_ideas or []) if s]
        own = concept.summary_line().casefold()
        for other in siblings:
            if other == own:
                continue
            overlap = len(set(own.split()) & set(other.split()))
            if overlap >= 4:
                originality -= 12.0
            elif overlap >= 2:
                originality -= 5.0

        # Hook / title quality
        title_words = [w for w in concept.title.split() if w.strip()]
        if 2 <= len(title_words) <= 5:
            ctr += 10.0
            curiosity += 6.0
            strength += 6.0
        elif len(title_words) > 6:
            ctr -= 8.0
            strength -= 6.0

        if concept.lighting:
            visual_impact += 5.0
            composition += 4.0

        scores = ConceptScores(
            curiosity=_clamp(curiosity),
            mystery=_clamp(mystery),
            visual_impact=_clamp(visual_impact),
            ctr_potential=_clamp(ctr),
            originality=_clamp(originality),
            storytelling=_clamp(storytelling),
            brand_match=_clamp(brand_match),
            emotion=_clamp(emotion_score),
            composition=_clamp(composition),
            thumbnail_strength=_clamp(strength),
        )
        scores.recompute_overall()
        return scores


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)
