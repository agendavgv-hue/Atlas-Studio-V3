"""Image Prompt Builder — Scene Blueprint → AI scene prompts (no text/logo)."""

from __future__ import annotations

from app.creative.engine.brief import CreativeBrief
from app.creative.engine.prompts import create_thumbnail_prompt
from app.creative.engine.style_profile import StyleProfile
from app.thumbnail.concepts.models import ThumbnailConceptIdea
from app.thumbnail.pipeline.plan import ThumbnailPlan
from app.thumbnail.prompt_builder import THUMBNAIL_VARIANTS, ThumbnailPromptPlan
from app.thumbnail.scene_director.models import SceneBlueprint
from app.thumbnail.style_dna.models import ThumbnailStyleDNA
from app.thumbnail.critic_engine.models import ImprovePlan

_NO_BRANDING_NEGATIVE = (
    "text, letters, words, typography, title, caption, subtitle, watermark, logo, "
    "signature, frame border, ui, interface, collage, split screen, cartoon, anime, "
    "illustration, deformed, blurry, lowres, jpeg artifacts, stock photo look, "
    "lone object on table, still life product shot, empty landscape without story"
)

_VARIANT_NUDGES = {
    "A": "lean into mystery and unanswered questions",
    "B": "lean into epic scale and grandeur",
    "C": "lean into documentary realism and evidence feel",
    "D": "lean into dramatic light and tension",
}


def build_pipeline_prompt_plans(
    brief: CreativeBrief,
    plan: ThumbnailPlan,
    *,
    thumbnail_profile: StyleProfile | None = None,
    image_profile: StyleProfile | None = None,
    critic_notes: str = "",
    best_concept: ThumbnailConceptIdea | None = None,
    scene_blueprint: SceneBlueprint | None = None,
    style_dna: ThumbnailStyleDNA | None = None,
    improve_plan: ImprovePlan | None = None,
) -> list[ThumbnailPromptPlan]:
    """Prompts are driven by Scene Blueprint (+ plan layout). Never invent a lone object."""
    subject = (
        (scene_blueprint.main_subject if scene_blueprint else "")
        or plan.main_subject
    )
    master = create_thumbnail_prompt(brief, subject=subject)
    profile_block = ""
    if style_dna is not None:
        profile_block += "\n\n" + style_dna.prompt_block()
    elif thumbnail_profile is not None:
        profile_block += "\n\n" + thumbnail_profile.prompt_block()
    if image_profile is not None and image_profile.reference_count > 0:
        profile_block += "\n\nIMAGE REFERENCE STYLE\n" + image_profile.prompt_block()

    scene_block = ""
    if scene_blueprint is not None:
        scene_block = "\n\n" + scene_blueprint.prompt_block()
    elif best_concept is not None:
        scene_block = "\n\n" + best_concept.prompt_block()

    story = brief.story
    story_bits = []
    for attr in (
        "storytelling_style",
        "hook_style",
        "pacing",
        "emotion",
        "ending_style",
        "hook_type",
    ):
        value = getattr(story, attr, None)
        if value:
            story_bits.append(f"{attr}: {value}")
    for attr in ("mystery", "wonder", "documentary_level"):
        value = getattr(story, attr, None)
        if value is not None:
            story_bits.append(f"{attr}: {float(value):.0f}")
    story_line = "; ".join(story_bits) if story_bits else "premium documentary storytelling"

    rules = []
    for rule in brief.enabled_rules[:12]:
        rules.append(f"- {rule.title}: {(rule.description or '')[:120]}")
    rules_block = "\n".join(rules) if rules else "- Follow channel creative rules strictly."

    brand_colors = ", ".join(
        c
        for c in (
            brief.brand.primary_color,
            brief.brand.secondary_color,
            brief.brand.accent_color,
        )
        if c
    )

    critic_block = ""
    if improve_plan is not None and improve_plan.summary_lines:
        critic_block = "\n\n" + improve_plan.prompt_block()
    if critic_notes.strip():
        critic_block += (
            "\n\nCRITIC FEEDBACK (must improve on previous attempt):\n"
            + critic_notes.strip()
        )

    authority = (
        "SCENE BLUEPRINT"
        if scene_blueprint is not None
        else "BEST THUMBNAIL CONCEPT"
    )
    base = (
        f"{master}{profile_block}{scene_block}\n\n"
        f"{plan.prompt_block()}\n\n"
        "STORY DNA\n"
        f"{story_line}\n\n"
        "CREATIVE RULES\n"
        f"{rules_block}\n\n"
        "IMAGE DNA\n"
        f"Lighting: {(scene_blueprint.lighting if scene_blueprint else '') or brief.image.lighting or plan.lighting}\n"
        f"Camera: {(scene_blueprint.camera if scene_blueprint else '') or brief.image.camera_style or plan.camera_angle}\n"
        f"Mood: {(scene_blueprint.emotion if scene_blueprint else '') or brief.image.mood or plan.emotion}\n"
        f"Atmosphere: {(scene_blueprint.atmosphere if scene_blueprint else '') or brief.image.atmosphere or 'cinematic documentary'}\n"
        f"Texture: {brief.image.texture or 'natural filmic texture'}\n\n"
        f"Brand color grading: {brand_colors or 'channel palette'}.\n"
        f"CRITICAL: Generate ONLY the photographic scene from the {authority} above. "
        "Tell that exact story — person/vehicle + mysterious object + epic background + emotion. "
        "Do NOT invent a different story. "
        "Do NOT generate a lone object, still-life, or empty landscape. "
        "Do NOT paint any text, letters, titles, logos, frames, watermarks, or branding. "
        "Leave clear negative space for Atlas typography and logo composite.\n"
        "Use uploaded reference thumbnails as the primary visual style. "
        "Maintain the same cinematic composition, lighting, typography spacing, "
        "and premium documentary atmosphere. Follow the same visual identity."
        f"{critic_block}"
    ).strip()

    negative = _NO_BRANDING_NEGATIVE
    for rule in brief.enabled_rules:
        title = rule.title.casefold()
        if "cartoon" in title:
            negative += ", cartoon, anime"
        if "clutter" in title or "one main" in title or "one dominant" in title:
            negative += ", cluttered, busy collage, multiple competing subjects"

    plans: list[ThumbnailPromptPlan] = []
    for variant_id, key, label in THUMBNAIL_VARIANTS:
        nudge = _VARIANT_NUDGES.get(variant_id, label)
        prompt = (
            f"{base}\n\nVARIANT {variant_id} ({label}): {nudge}. "
            f"Still obey {authority}, Thumbnail Plan, Creative Director, "
            f"and reference style exactly."
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
