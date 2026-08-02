"""Master prompt builders — generators must not invent prompts themselves."""

from __future__ import annotations

from app.creative.engine.brief import CreativeBrief
from app.creative.engine import layers


def master_prompt(
    brief: CreativeBrief,
    *,
    domain: str,
    subject: str = "",
    include_project: bool = True,
) -> str:
    """Build the layered Creative Director master prompt for a domain."""
    blocks = [
        "=== CREATIVE DIRECTOR MASTER PROMPT ===",
        "LAYER 1 — CHANNEL IDENTITY\n" + layers.layer_channel_identity(brief),
        "LAYER 2 — BRAND KIT\n" + layers.layer_brand_kit(brief),
    ]
    domain_key = (domain or "").strip().casefold()
    if domain_key in {"thumbnail", "all"}:
        blocks.append("LAYER 3 — THUMBNAIL DNA\n" + layers.layer_thumbnail_dna(brief))
    if domain_key in {"image", "thumbnail", "all"}:
        blocks.append("LAYER 4 — IMAGE DNA\n" + layers.layer_image_dna(brief))
    if domain_key in {"story", "script", "seo", "shorts", "all"}:
        blocks.append("LAYER 5 — STORY DNA\n" + layers.layer_story_dna(brief))
    if domain_key in {"movie", "all"}:
        blocks.append("LAYER 5B — MOVIE DNA\n" + layers.layer_movie_dna(brief))
    if domain_key in {"voice", "shorts", "all"}:
        blocks.append("LAYER 5C — VOICE DNA\n" + layers.layer_voice_dna(brief))
    if domain_key in {"music", "movie", "all"}:
        blocks.append("LAYER 5D — MUSIC DNA\n" + layers.layer_music_dna(brief))

    blocks.append("LAYER 6 — CREATIVE RULES\n" + layers.layer_creative_rules(brief))
    blocks.append("LAYER 7 — CHANNEL PERSONALITY\n" + layers.layer_personality(brief))
    if include_project:
        blocks.append("LAYER 8 — PROJECT\n" + layers.layer_project(brief))
    blocks.append("LAYER 9 — REFERENCES\n" + layers.layer_references(brief))

    if (subject or "").strip():
        blocks.append("SUBJECT / SCENE\n" + subject.strip())

    blocks.append(
        "FINAL INSTRUCTION\n"
        "Every decision must make the result instantly recognizable as this channel. "
        "Never produce generic stock AI looks. Obey Brand Kit, DNA, Rules, Personality, "
        "and References together."
    )
    return "\n\n".join(blocks)


def create_thumbnail_prompt(brief: CreativeBrief, *, subject: str = "") -> str:
    return master_prompt(brief, domain="thumbnail", subject=subject)


def create_image_prompt(brief: CreativeBrief, *, subject: str = "") -> str:
    return master_prompt(brief, domain="image", subject=subject)


def create_script_prompt(brief: CreativeBrief, *, subject: str = "") -> str:
    return master_prompt(brief, domain="script", subject=subject)


def create_shorts_prompt(brief: CreativeBrief, *, subject: str = "") -> str:
    return master_prompt(brief, domain="shorts", subject=subject)


def create_seo_prompt(brief: CreativeBrief, *, subject: str = "") -> str:
    return master_prompt(brief, domain="seo", subject=subject)


def create_movie_prompt(brief: CreativeBrief, *, subject: str = "") -> str:
    return master_prompt(brief, domain="movie", subject=subject)


def director_system_block(brief: CreativeBrief) -> str:
    """Compact system-layer brief for text providers (script/sheet)."""
    return master_prompt(brief, domain="script", include_project=True)
