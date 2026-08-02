"""Layered Creative Director prompt text (generic — driven by Channel Studio)."""

from __future__ import annotations

from app.creative.engine.brief import CreativeBrief


def layer_channel_identity(brief: CreativeBrief) -> str:
    g = brief.general
    traits = []
    for key, value in sorted(brief.personality.traits.items(), key=lambda kv: -kv[1]):
        if value >= 70:
            traits.append(key)
    trait_line = ", ".join(traits[:8]) if traits else "premium documentary"
    return (
        f"You are creating content for {brief.channel_name}.\n"
        f"Channel type: {g.channel_type or 'documentary'}.\n"
        f"Niche: {g.niche or 'premium documentary'}.\n"
        f"Audience: {g.audience or 'curious adults'}.\n"
        f"Tone of voice: {g.tone_of_voice or 'calm documentary'}.\n"
        f"Identity keywords: {trait_line}.\n"
        f"Description: {(g.description or '').strip() or 'A distinct branded channel.'}"
    )


def layer_brand_kit(brief: CreativeBrief) -> str:
    b = brief.brand
    colors = ", ".join(
        c for c in (b.primary_color, b.secondary_color, b.accent_color) if c
    )
    fonts = ", ".join(b.fonts) if b.fonts else ""
    parts = [
        "BRAND KIT — preserve visual identity.",
        f"Logo asset: {'set' if b.logo else 'not set'}.",
        f"Thumbnail logo: {'set' if b.thumbnail_logo else 'not set'}.",
        f"Thumbnail frame: {'set' if getattr(b, 'thumbnail_frame', '') else 'not set'} "
        "(composited after AI — never generate frames).",
        f"Watermark: {'set' if b.watermark else 'not set'}.",
    ]
    if colors:
        parts.append(f"Brand colors: {colors}.")
    if fonts:
        parts.append(f"Fonts: {fonts}.")
    if b.cta:
        parts.append(f"CTA: {b.cta}")
    return "\n".join(parts)


def layer_thumbnail_dna(brief: CreativeBrief) -> str:
    t = brief.thumbnail
    return (
        "THUMBNAIL DNA\n"
        f"Dominant subject count: {t.dominant_subject}\n"
        f"Emotion: {t.emotion}\n"
        f"Composition: {t.composition_style}\n"
        f"Negative space: {t.negative_space}\n"
        f"Logo visible: {t.logo_visible}; position: {t.logo_position}\n"
        f"Max words on thumbnail: {t.max_words}\n"
        f"Contrast preference: {t.contrast}\n"
        f"Cinematic level: {t.cinematic_level:.0f}/100\n"
        f"Realism: {t.realism:.0f}/100\n"
        f"Documentary feel: {t.documentary:.0f}/100\n"
        f"Creativity: {t.creativity:.0f}/100\n"
        f"Style strength: {t.style_strength:.0f}/100\n"
        f"Brand strength: {t.brand_strength:.0f}/100"
    )


def layer_image_dna(brief: CreativeBrief) -> str:
    i = brief.image
    return (
        "IMAGE DNA\n"
        f"Lighting: {i.lighting}\n"
        f"Camera style: {i.camera_style}\n"
        f"Mood: {i.mood}\n"
        f"Atmosphere: {i.atmosphere}\n"
        f"Texture: {i.texture}\n"
        f"Film grain: {i.film_grain}\n"
        f"Realism: {i.realism:.0f}/100\n"
        f"Resolution: {i.resolution}\n"
        f"Quality: {i.image_quality}"
    )


def layer_story_dna(brief: CreativeBrief) -> str:
    s = brief.story
    return (
        "STORY DNA\n"
        f"Hook type: {s.hook_type}\n"
        f"Emotion: {s.emotion}\n"
        f"Cliffhangers: {s.cliffhangers}\n"
        f"Ending style: {s.ending_style}\n"
        f"Mystery {s.mystery:.0f} · Wonder {s.wonder:.0f} · Science {s.science:.0f} · "
        f"History {s.history:.0f} · Adventure {s.adventure:.0f} · Fantasy {s.fantasy:.0f}\n"
        f"Suspense {s.suspense:.0f} · Speculation {s.speculation:.0f} · "
        f"Historical accuracy {s.historical_accuracy:.0f}\n"
        f"Open questions {s.open_questions:.0f} · Tension {s.tension:.0f} · "
        f"Documentary {s.documentary_level:.0f}"
    )


def layer_movie_dna(brief: CreativeBrief) -> str:
    m = brief.movie
    return (
        "MOVIE DNA\n"
        f"Preset: {m.preset}\n"
        f"Camera motion: {m.camera_motion}\n"
        f"Particles: {m.particles}\n"
        f"Lighting: {m.lighting_preset or m.lighting}\n"
        f"Shot style: {m.shot_style}"
    )


def layer_voice_dna(brief: CreativeBrief) -> str:
    v = brief.voice
    return (
        "VOICE DNA\n"
        f"Style: {v.voice_style}\n"
        f"Accent: {v.accent}\n"
        f"Age feel: {v.age}\n"
        f"Authority {v.authority:.0f} · Warmth {v.warmth:.0f} · "
        f"Curiosity {v.curiosity:.0f} · Mystery {v.mystery:.0f} · Energy {v.energy:.0f}"
    )


def layer_music_dna(brief: CreativeBrief) -> str:
    m = brief.music
    return (
        "MUSIC DNA\n"
        f"Personality: {m.personality or m.mood}\n"
        f"Volume: {m.volume:.2f}\n"
        f"Background level: {m.background_level:.2f}\n"
        f"Ducking: {m.ducking}"
    )


def layer_creative_rules(brief: CreativeBrief) -> str:
    rules = brief.enabled_rules
    if not rules:
        return "CREATIVE RULES\nNo enabled rules."
    lines = ["CREATIVE RULES — obey every enabled rule:"]
    for rule in sorted(rules, key=lambda r: -r.priority):
        lines.append(f"- [{rule.category}] {rule.title}: {rule.description}")
    return "\n".join(lines)


def layer_personality(brief: CreativeBrief) -> str:
    lines = ["CHANNEL PERSONALITY (0–100 — stronger values dominate):"]
    for key, value in sorted(brief.personality.traits.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {key}: {value:.0f}")
    return "\n".join(lines)


def layer_project(brief: CreativeBrief) -> str:
    p = brief.project
    parts = ["PROJECT CONTEXT"]
    if p.topic:
        parts.append(f"Topic: {p.topic}")
    if p.idea:
        parts.append(f"Idea: {p.idea}")
    if p.primary_subject:
        parts.append(f"Main subject: {p.primary_subject}")
    if p.primary_location:
        parts.append(f"Main location: {p.primary_location}")
    if p.primary_emotion:
        parts.append(f"Main emotion: {p.primary_emotion}")
    if p.script_excerpt:
        parts.append(f"Script excerpt:\n{p.script_excerpt[:800]}")
    return "\n".join(parts)


def layer_references(brief: CreativeBrief) -> str:
    if brief.reference_count <= 0:
        return (
            "REFERENCES\nNo uploaded references yet. "
            "Still follow Brand Kit, DNA, rules, and personality."
        )
    lines = [
        "REFERENCES — match the uploaded channel references:",
        "Composition, lighting, typography, and premium identity must resemble the references.",
    ]
    for item in brief.references:
        if item.count <= 0:
            continue
        sample = ", ".join(item.names[:5]) if item.names else ""
        lines.append(f"- {item.kind}: {item.count} file(s)" + (f" ({sample})" if sample else ""))
    return "\n".join(lines)


def compact_image_look(brief: CreativeBrief) -> str:
    """Short Stable-Diffusion-friendly look pack from Channel Studio."""
    i = brief.image
    t = brief.thumbnail
    parts = [
        f"{brief.channel_name} house style",
        i.lighting.replace("_", " "),
        i.camera_style.replace("_", " "),
        i.mood,
        i.atmosphere if i.atmosphere != "none" else "",
        i.texture,
        f"film grain {i.film_grain}" if i.film_grain != "off" else "",
        f"realism {i.realism:.0f}",
        f"cinematic {t.cinematic_level:.0f}",
        brief.brand.primary_color,
        brief.brand.secondary_color,
    ]
    # Personality keywords above threshold
    for key, value in brief.personality.traits.items():
        if value >= 75:
            parts.append(key)
    return ", ".join(p for p in parts if p and str(p).strip())


def rule_negative_hints(brief: CreativeBrief) -> str:
    hints: list[str] = []
    for rule in brief.enabled_rules:
        title = rule.title.casefold()
        if "cartoon" in title or "anime" in rule.description.casefold():
            hints.append("cartoon, anime, illustration, drawing")
        if "clutter" in title or "clutter" in rule.description.casefold():
            hints.append("cluttered composition, busy collage")
        if "bright" in title:
            hints.append("neon colors, oversaturated palette")
    return ", ".join(dict.fromkeys(hints))
