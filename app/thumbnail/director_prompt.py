"""Primary thumbnail prompts from Creative Director + reference style profiles."""

from __future__ import annotations

from app.creative.engine.brief import CreativeBrief
from app.creative.engine.prompts import create_thumbnail_prompt
from app.creative.engine.style_profile import StyleProfile
from app.thumbnail.prompt_builder import ThumbnailPromptPlan, THUMBNAIL_VARIANTS


_NO_TEXT_NEGATIVE = (
    "text, letters, words, typography, title, caption, subtitle, watermark, logo, "
    "signature, ui, interface, collage, split screen, cartoon, anime, illustration, "
    "deformed, blurry, lowres, jpeg artifacts"
)


def build_director_led_thumbnail_plans(
    brief: CreativeBrief,
    *,
    hero_subject: str,
    hook: str,
    emotion: str = "",
    thumbnail_profile: StyleProfile | None = None,
    image_profile: StyleProfile | None = None,
) -> list[ThumbnailPromptPlan]:
    """Creative Director master prompt is PRIMARY; variants only nudge emotion."""
    hero = (hero_subject or "").strip() or "one dominant cinematic subject"
    master = create_thumbnail_prompt(brief, subject=hero)
    profile_block = ""
    if thumbnail_profile is not None:
        profile_block += "\n\n" + thumbnail_profile.prompt_block()
    if image_profile is not None and image_profile.reference_count > 0:
        profile_block += "\n\nIMAGE REFERENCES\n" + image_profile.prompt_block()

    no_text = (
        "CRITICAL: Do NOT paint any text, letters, titles, logos, or watermarks. "
        "Atlas will composite typography and logo after generation. "
        "Leave clear negative space for headline text."
    )
    brand_colors = ", ".join(
        c
        for c in (
            brief.brand.primary_color,
            brief.brand.secondary_color,
            brief.brand.accent_color,
        )
        if c
    )
    color_line = f"Brand color grading: {brand_colors}." if brand_colors else ""

    base = (
        f"{master}{profile_block}\n\n"
        f"HERO SUBJECT (must dominate the frame): {hero}\n"
        f"Scene emotion: {(emotion or brief.thumbnail.emotion or 'curiosity')}\n"
        f"{color_line}\n"
        f"{no_text}"
    ).strip()

    negative = _NO_TEXT_NEGATIVE
    rule_neg = []
    for rule in brief.enabled_rules:
        title = rule.title.casefold()
        if "cartoon" in title:
            rule_neg.append("cartoon, anime")
        if "clutter" in title or "one main" in title or "one dominant" in title:
            rule_neg.append("cluttered, busy collage, multiple competing subjects")
    if rule_neg:
        negative = negative + ", " + ", ".join(dict.fromkeys(rule_neg))

    plans: list[ThumbnailPromptPlan] = []
    for variant_id, key, label in THUMBNAIL_VARIANTS:
        prompt = (
            f"{base}\n\nVARIANT {variant_id} DIRECTION: {label}. "
            f"Still obey Creative Director identity and reference style exactly."
        )
        plans.append(
            ThumbnailPromptPlan(
                variant_id=variant_id,
                variant_key=key,
                variant_label=label,
                prompt=prompt,
                negative_prompt=negative,
            )
        )
    return plans
