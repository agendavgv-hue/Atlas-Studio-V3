"""Invent 5+ thumbnail concepts (AI preferred, heuristic fallback)."""

from __future__ import annotations

from app.creative.engine.brief import CreativeBrief
from app.creative.engine.style_profile import StyleProfile
from app.providers.base import TextProvider
from app.providers.errors import ProviderError
from app.thumbnail.concepts.models import ThumbnailConceptIdea
from app.thumbnail.text_utils import parse_json_object

MIN_CONCEPTS = 5

_SYSTEM = (
    "You are Atlas Studio's Thumbnail Concept Director. "
    "You think like a senior YouTube creative director. "
    "You invent multiple distinct thumbnail CONCEPTS — never image prompts, "
    "never logo/text instructions. Maximize curiosity and CTR."
)

_USER = """Channel: {channel}
Topic / project: {topic}

Channel personality (high traits):
{personality}

Story DNA:
{story}

Thumbnail / Image DNA hints:
{dna}

Reference style analysis:
{references}

Script excerpt:
---
{script}
---

Invent AT least {min_concepts} DISTINCT thumbnail concepts for this project.
Each concept must describe a complete visual idea with foreground, midground/background,
lighting, emotion, and a short curiosity hook (2–5 words, ALL CAPS).

Rules:
- Concepts must feel like THIS channel (personality + references), not generic stock AI.
- Prefer one dominant subject + clear negative space for title.
- Make concepts meaningfully different from each other.
- Do NOT write Stable Diffusion prompts.
- Do NOT include text, logos, frames, or watermarks in the scene description.

Return ONLY JSON:
{{
  "selected_scene": "highest click-value scene in one sentence",
  "click_value_reason": "why that scene wins",
  "concepts": [
    {{
      "id": 1,
      "title": "SHORT HOOK",
      "foreground": "dominant subject",
      "midground": "supporting element",
      "background": "environment",
      "lighting": "light description",
      "emotion": "curiosity|mystery|epic|adventure|wonder|fear",
      "elements": ["object1", "object2"],
      "hero_subject": "one iconic subject",
      "hook": "SHORT HOOK"
    }}
  ]
}}
"""


class ConceptInventor:
    """Create ≥5 thumbnail concepts for a project."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self._text = text_provider

    def invent(
        self,
        *,
        brief: CreativeBrief,
        script_text: str = "",
        topic: str = "",
        thumbnail_profile: StyleProfile | None = None,
        min_concepts: int = MIN_CONCEPTS,
    ) -> tuple[list[ThumbnailConceptIdea], str, str]:
        topic_text = (
            topic
            or brief.project.topic
            or brief.project.idea
            or brief.channel_name
            or "Untitled"
        ).strip()
        try:
            if self._text is not None and (script_text or topic_text).strip():
                return self._invent_with_ai(
                    brief=brief,
                    script_text=script_text,
                    topic=topic_text,
                    thumbnail_profile=thumbnail_profile,
                    min_concepts=min_concepts,
                )
        except (ProviderError, Exception):  # noqa: BLE001
            pass
        concepts = self._invent_heuristic(
            brief=brief,
            topic=topic_text,
            script_text=script_text,
            thumbnail_profile=thumbnail_profile,
            min_concepts=min_concepts,
        )
        return concepts, topic_text, "Heuristic concepts from topic + Channel DNA"


    def _invent_with_ai(
        self,
        *,
        brief: CreativeBrief,
        script_text: str,
        topic: str,
        thumbnail_profile: StyleProfile | None,
        min_concepts: int,
    ) -> tuple[list[ThumbnailConceptIdea], str, str]:
        assert self._text is not None
        traits = sorted(
            ((k, v) for k, v in (brief.personality.traits or {}).items() if v >= 60),
            key=lambda kv: -kv[1],
        )
        personality = ", ".join(f"{k}:{v:.0f}" for k, v in traits[:10]) or "premium documentary"
        story = (
            f"style={brief.story.storytelling_style}; emotion={brief.story.emotion}; "
            f"mystery={brief.story.mystery:.0f}; wonder={brief.story.wonder:.0f}; "
            f"hook={brief.story.hook_style}"
        )
        dna = (
            f"thumb emotion={brief.thumbnail.emotion}; contrast={brief.thumbnail.contrast}; "
            f"image lighting={brief.image.lighting}; mood={brief.image.mood}; "
            f"atmosphere={brief.image.atmosphere}"
        )
        refs = "No reference profile yet."
        if thumbnail_profile is not None:
            refs = (
                f"refs={thumbnail_profile.reference_count}; "
                f"subject_bias={thumbnail_profile.subject_bias}; "
                f"negative_space={thumbnail_profile.negative_space}; "
                f"contrast={thumbnail_profile.contrast}; "
                f"brightness={thumbnail_profile.brightness}; "
                f"temperature={thumbnail_profile.color_temperature}; "
                f"mood={thumbnail_profile.mood}; "
                f"camera={thumbnail_profile.camera_angle}"
            )
        prompt = _USER.format(
            channel=brief.channel_name,
            topic=topic,
            personality=personality,
            story=story,
            dna=dna,
            references=refs,
            script=(script_text or topic)[:9000],
            min_concepts=max(MIN_CONCEPTS, int(min_concepts)),
        )
        raw = self._text.generate_text(prompt, system=_SYSTEM)
        data = parse_json_object(raw, label="Thumbnail Concept Planner")
        concepts = _parse_concepts(data.get("concepts"), min_count=min_concepts)
        if len(concepts) < min_concepts:
            concepts.extend(
                self._invent_heuristic(
                    brief=brief,
                    topic=topic,
                    script_text=script_text,
                    thumbnail_profile=thumbnail_profile,
                    min_concepts=min_concepts,
                )[len(concepts) :]
            )
        scene = str(data.get("selected_scene") or topic).strip()
        reason = str(data.get("click_value_reason") or "").strip()
        return concepts[: max(min_concepts, len(concepts))], scene, reason

    def _invent_heuristic(
        self,
        *,
        brief: CreativeBrief,
        topic: str,
        script_text: str = "",
        thumbnail_profile: StyleProfile | None = None,
        min_concepts: int = MIN_CONCEPTS,
    ) -> list[ThumbnailConceptIdea]:
        subject = (
            brief.project.primary_subject
            or _first_nounish(topic)
            or "iconic discovery"
        )
        place = brief.project.primary_location or "dramatic landscape"
        emotion = brief.thumbnail.emotion or brief.story.emotion or "curiosity"
        lighting = brief.image.lighting or "cinematic rim light"
        if thumbnail_profile and thumbnail_profile.brightness == "dark":
            lighting = f"low-key {lighting}"

        templates = [
            {
                "title": "WHAT HIDES HERE?",
                "foreground": f"giant {subject} filling the foreground",
                "midground": f"tiny human figure for scale near {place}",
                "background": f"storm-lit {place}",
                "lighting": f"golden shafts through dark clouds, {lighting}",
                "emotion": "curiosity",
                "elements": [subject, "scale figure", "storm", "gold light"],
            },
            {
                "title": "THEY VANISHED",
                "foreground": "explorer silhouette looking outward",
                "midground": f"vanishing {subject}",
                "background": f"mist over {place}",
                "lighting": "soft misty backlight",
                "emotion": "mystery",
                "elements": ["explorer", subject, "mist", place],
            },
            {
                "title": "ANCIENT PROOF",
                "foreground": "old map and brass compass",
                "midground": "burning lantern glow",
                "background": f"storm beyond {place}",
                "lighting": "warm lantern against cold storm light",
                "emotion": "adventure",
                "elements": ["map", "lantern", "compass", "storm"],
            },
            {
                "title": "TOO LATE?",
                "foreground": f"towering wave or force near {subject}",
                "midground": "fragile vessel or structure",
                "background": "lightning sky",
                "lighting": "harsh lightning contrast",
                "emotion": "mystery",
                "elements": ["wave", subject, "lightning"],
            },
            {
                "title": "LOST FOREVER",
                "foreground": "abandoned landmark silhouette",
                "midground": f"weathered remnant of {subject}",
                "background": f"fogbound {place}",
                "lighting": "pale cold dawn mist",
                "emotion": "wonder",
                "elements": ["landmark", "fog", subject, "ruin"],
            },
            {
                "title": "NOT NATURAL",
                "foreground": f"impossible detail on {subject}",
                "midground": "evidence markers / tools",
                "background": "documentary field site",
                "lighting": lighting,
                "emotion": "discovery",
                "elements": [subject, "evidence", "site"],
            },
        ]

        # Bias titles/emotions toward top personality traits.
        traits = [
            k for k, v in sorted((brief.personality.traits or {}).items(), key=lambda kv: -kv[1])
            if v >= 75
        ]
        if "epic" in traits and templates:
            templates[3]["emotion"] = "epic"
            templates[3]["title"] = "UNSTOPPABLE"
        if "history" in traits:
            templates[2]["title"] = "WHO BUILT THIS?"
        if "science" in traits:
            templates[5]["title"] = "THE EVIDENCE"

        concepts: list[ThumbnailConceptIdea] = []
        for i, tmpl in enumerate(templates[: max(min_concepts, MIN_CONCEPTS)], start=1):
            concepts.append(
                ThumbnailConceptIdea(
                    id=i,
                    title=str(tmpl["title"]),
                    foreground=str(tmpl["foreground"]),
                    midground=str(tmpl["midground"]),
                    background=str(tmpl["background"]),
                    lighting=str(tmpl["lighting"]),
                    emotion=str(tmpl.get("emotion") or emotion),
                    elements=list(tmpl.get("elements") or []),
                    hero_subject=subject,
                    hook=str(tmpl["title"]),
                    idea="; ".join(
                        p
                        for p in (
                            tmpl["foreground"],
                            tmpl["midground"],
                            tmpl["background"],
                        )
                        if p
                    ),
                )
            )
        # Seed a bit of script context into first concept if available.
        if script_text and concepts:
            snippet = " ".join(script_text.split()[:12])
            if snippet:
                concepts[0].notes.append(f"script seed: {snippet}")
        return concepts


def _parse_concepts(raw: object, *, min_count: int) -> list[ThumbnailConceptIdea]:
    items = raw if isinstance(raw, list) else []
    concepts: list[ThumbnailConceptIdea] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        concept = ThumbnailConceptIdea.from_dict(item, default_id=i)
        if not concept.hero_subject:
            concept.hero_subject = concept.foreground or concept.title
        if not concept.hook:
            concept.hook = concept.title
        if not concept.elements:
            concept.elements = [
                p
                for p in (concept.foreground, concept.midground, concept.background)
                if p
            ][:4]
        concepts.append(concept)
    return concepts[: max(min_count, len(concepts))]


def _first_nounish(text: str) -> str:
    words = [w.strip(".,:;!?\"'") for w in (text or "").split() if w.strip()]
    skip = {"the", "a", "an", "of", "and", "in", "on", "to", "for"}
    for word in words:
        if word.casefold() not in skip and len(word) > 2:
            return word
    return text.strip()[:40]
