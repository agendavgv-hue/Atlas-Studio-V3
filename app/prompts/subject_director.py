"""Subject Director — subject world always leads channel style.

Determines location, climate, era, architecture, landscape, flora/fauna,
materials, culture, and historical context BEFORE Channel Director styling.
"""

from __future__ import annotations

import re

# Keyword → subject-world vocabulary (only applied when the scene matches).
_SUBJECT_WORLDS: tuple[tuple[tuple[str, ...], str, tuple[str, ...]], ...] = (
    (
        ("antarctica", "antarctic", "south pole", "polar ice", "ice shelf"),
        (
            "Antarctic subject world: gigantic ice fields, glaciers, snowstorms, "
            "polar mist, frozen mountain ranges, ice caves, subglacial tunnels, "
            "ice fractures, ice walls, polar research / scientific expeditions when "
            "fitting, aurora only when appropriate — keep cold white-blue ice reality"
        ),
        (
            "Egyptian tombs",
            "deserts",
            "jungle",
            "tropical temples",
            "tropical ruins",
            "sandstone pyramids",
            "palm oasis",
        ),
    ),
    (
        ("arctic", "north pole", "greenland ice", "tundra"),
        (
            "Arctic subject world: pack ice, tundra, polar mist, frozen coastlines, "
            "icebergs, harsh cold light, expedition gear when fitting"
        ),
        ("Egyptian tombs", "deserts", "tropical jungle", "temples", "rainforest"),
    ),
    (
        ("egypt", "egyptian", "nile", "pharaoh", "pyramid", "giza", "valley of the kings"),
        (
            "Egyptian subject world: Nile valley or desert plateau, sandstone and "
            "limestone architecture, period-accurate temples/tombs/reliefs, linen, "
            "bronze tools, dry desert vegetation — historically grounded"
        ),
        ("Antarctic ice", "glaciers", "polar storms", "skyscrapers", "neon city"),
    ),
    (
        ("atlantis", "underwater city", "sunken city", "lost harbor"),
        (
            "Sunken/ancient maritime subject world: submerged stone architecture, "
            "sediment, kelp, shafts of underwater light, coral on carved stone, "
            "harbor geometry — keep the named place's mythology coherent"
        ),
        ("modern skyscrapers", "neon cyberpunk streets", "tropical beach resort"),
    ),
    (
        ("rome", "roman", "colosseum", "forum"),
        (
            "Roman subject world: travertine and marble, arches, forums, period "
            "armor/togas when people appear, Mediterranean vegetation, historically "
            "grounded architecture"
        ),
        ("Egyptian pyramids", "neon cities", "medieval castles unless named"),
    ),
    (
        ("space", "orbit", "spacecraft", "mars", "lunar", "nasa"),
        (
            "Space / near-future aerospace subject world: vacuum black, planetary "
            "surfaces or orbital craft, technical materials, mission hardware — "
            "keep the named mission/place true"
        ),
        ("ancient temples", "desert tombs", "medieval villages"),
    ),
    (
        ("lab", "laboratory", "cleanroom", "chip", "semiconductor", "robot", "ai server"),
        (
            "Premium tech facility subject world: cleanrooms, precision machines, "
            "glass, brushed metal, controlled lighting, modern industrial design"
        ),
        ("ancient ruins", "dusty tombs", "jungle temples", "medieval workshops"),
    ),
)


_VISUAL_STORYTELLING = (
    "VISUAL STORYTELLING: clear foreground, interesting midground, epic background, "
    "sense of scale, human scale reference when fitting, leading lines, cinematic "
    "composition — tell a story beat, not just a pretty object"
)

_HISTORICAL_ACCURACY = (
    "HISTORICAL ACCURACY: when the subject is historical, use period-fitting clothing, "
    "materials, architecture, tools, landscape, vegetation, and colors — avoid random "
    "anachronistic AI props"
)

_SUBJECT_LOCK = (
    "SUBJECT DIRECTOR LOCK: the subject determines content — location, climate, era, "
    "architecture, landscape, flora, fauna, materials, culture, historical context. "
    "Never swap in an unrelated biome or civilization"
)


def build_subject_director_block(scene: str) -> str:
    """Build the Subject Director layer that must lead every image prompt."""
    scene_text = " ".join((scene or "").split()).strip()
    if not scene_text:
        return (
            f"{_SUBJECT_LOCK}. {_VISUAL_STORYTELLING}. {_HISTORICAL_ACCURACY}"
        )

    parts = [
        _SUBJECT_LOCK,
        f"SUBJECT CONTENT: {scene_text}",
    ]
    world, _forbidden = match_subject_world(scene_text)
    if world:
        parts.append(world)
    parts.append(_VISUAL_STORYTELLING)
    parts.append(_HISTORICAL_ACCURACY)
    return ". ".join(parts)


def match_subject_world(scene: str) -> tuple[str, tuple[str, ...]]:
    """Return (world vocabulary, forbidden off-topic cues) for the scene."""
    lowered = f" {(scene or '').casefold()} "
    for keys, world, forbidden in _SUBJECT_WORLDS:
        if any(re.search(rf"(?<!\w){re.escape(key)}(?!\w)", lowered) for key in keys):
            return world, forbidden
    return "", ()


def subject_protection_negatives(scene: str) -> str:
    """Negatives that block off-topic biome/civilization swaps."""
    _world, forbidden = match_subject_world(scene)
    base = (
        "unrelated biome swap, wrong civilization, off-topic landmarks, "
        "subject replaced by generic stock location, anachronistic random props"
    )
    if not forbidden:
        return base
    return base + ", " + ", ".join(forbidden)


def subject_word_emphasis(scene: str) -> str:
    """Short lead phrase putting the raw subject first."""
    text = " ".join((scene or "").split()).strip()
    if not text:
        return ""
    return text
