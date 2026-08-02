"""Axis scoring heuristics for Thumbnail Critic (generic, channel-agnostic)."""

from __future__ import annotations

from typing import Any

from app.creative.engine.brief import CreativeBrief
from app.thumbnail.critic_engine.models import AxisCritique, CRITIC_AXES
from app.thumbnail.pipeline.plan import ThumbnailPlan
from app.thumbnail.pipeline.reference_compare import ReferenceSimilarityReport
from app.thumbnail.scene_director.models import SceneBlueprint
from app.thumbnail.style_dna.models import ThumbnailStyleDNA


def score_all_axes(
    *,
    brief: CreativeBrief,
    plan: ThumbnailPlan,
    similarity: ReferenceSimilarityReport,
    hook: str,
    prompt: str,
    has_logo: bool,
    has_frame: bool,
    composed: bool,
    scene_blueprint: SceneBlueprint | None = None,
    style_dna: ThumbnailStyleDNA | None = None,
    assets: Any | None = None,
) -> list[AxisCritique]:
    blob = f"{prompt} {plan.story_focus} {plan.emotion}".casefold()
    story_blob = (
        (scene_blueprint.story if scene_blueprint else "")
        + " "
        + plan.story_focus
    ).casefold()
    words = [w for w in (hook or "").split() if w.strip()]
    max_words = int(
        (style_dna.average_words if style_dna else 0) or brief.thumbnail.max_words or 4
    )
    axes: list[AxisCritique] = []

    # Storytelling
    story = 60.0
    if scene_blueprint and scene_blueprint.meets_minimum_rules():
        story += 22.0
    elif plan.main_subject and plan.secondary_subject and plan.background:
        story += 16.0
    else:
        story -= 10.0
    if len((scene_blueprint.story if scene_blueprint else plan.story_focus).split()) >= 10:
        story += 8.0
    axes.append(
        _axis(
            "storytelling",
            story,
            why=(
                "Scene tells a clear beat with actor + mystery object + background."
                if story >= 80
                else "Story feels thin — too close to a still-life or lone object."
            ),
            improvement=(
                "Keep the locked Scene Blueprint story intact."
                if story >= 80
                else "Ensure person/vehicle + mysterious object + epic background in one beat."
            ),
        )
    )

    # Curiosity / Mystery
    curiosity = 62.0
    mystery = 62.0
    for token in ("impossible", "secret", "vanish", "hidden", "unanswered", "mystery"):
        if token in story_blob or token in blob:
            curiosity += 6.0
            mystery += 5.0
    emotion = (plan.emotion or "").casefold()
    if any(k in emotion for k in ("mystery", "curiosity", "wonder", "danger")):
        curiosity += 10.0
        mystery += 12.0
    mystery += float(getattr(brief.story, "mystery", 70) or 70) * 0.12
    curiosity += float(getattr(brief.story, "wonder", 70) or 70) * 0.08
    axes.append(
        _axis(
            "curiosity",
            curiosity,
            why=(
                "Unanswered question / impossible beat is visible."
                if curiosity >= 75
                else "Er gebeurt niets onverwachts."
            ),
            improvement=(
                "Preserve the curiosity hook in the scene."
                if curiosity >= 75
                else "Voeg een mysterieus element toe dat een vraag opwerpt."
            ),
        )
    )
    axes.append(
        _axis(
            "mystery",
            mystery,
            why=(
                "Mystery emotion and story DNA align."
                if mystery >= 75
                else "Mystery signal is weak in scene or emotion."
            ),
            improvement=(
                "Keep fog/secret/impossible cues."
                if mystery >= 75
                else "Amplify mystery lighting and an unexplained object."
            ),
        )
    )

    # CTR
    ctr = 68.0
    if plan.main_subject:
        ctr += 8.0
    if words and len(words) <= max_words:
        ctr += 10.0
    elif not words:
        ctr -= 25.0
    if curiosity >= 75:
        ctr += 6.0
    axes.append(
        _axis(
            "ctr_potential",
            ctr,
            why=(
                "Strong subject + short hook + curiosity."
                if ctr >= 80
                else "CTR ingredients are incomplete."
            ),
            improvement=(
                "Keep hook punchy and subject dominant."
                if ctr >= 80
                else "Shorten hook and enlarge the main subject."
            ),
        )
    )

    # Brand
    brand = 68.0
    if brief.brand.primary_color or brief.brand.secondary_color:
        brand += 10.0
    if has_logo and brief.thumbnail.logo_visible:
        brand += 10.0
    elif brief.thumbnail.logo_visible and not has_logo:
        brand -= 18.0
    if has_frame:
        brand += 4.0
    brand += float(brief.thumbnail.brand_strength or 85) * 0.05
    axes.append(
        _axis(
            "brand_consistency",
            brand,
            why=(
                "Brand colors/logo/frame present."
                if brand >= 80
                else "Brand assets or colors are incomplete."
            ),
            improvement=(
                "Maintain Brand Kit overlays."
                if brand >= 80
                else "Ensure logo/frame from Channel Studio and brand grading."
            ),
        )
    )

    # Composition / negative space / subject
    composition = 70.0 + float(similarity.composition) * 0.18
    if plan.rule_of_thirds:
        composition += 6.0
    if style_dna and style_dna.rule_of_thirds:
        composition += 4.0
    neg_score = 72.0
    learned_neg = style_dna.negative_space if style_dna else plan.negative_space
    if plan.negative_space and learned_neg and plan.negative_space == learned_neg:
        neg_score += 14.0
    elif plan.negative_space:
        neg_score += 6.0
    else:
        neg_score -= 12.0
    subject = 70.0
    if plan.main_subject:
        subject += 12.0
    if style_dna and plan.extras.get("scene_id"):
        subject += 6.0
    if "center" in (plan.focal_point or "").casefold() and style_dna and style_dna.subject_position != "center":
        subject -= 10.0
        composition -= 8.0
    axes.append(
        _axis(
            "composition",
            composition,
            why=(
                "Rule-of-thirds / plan composition respected."
                if composition >= 78
                else "Onderwerp zit te dicht in het midden of mist hiërarchie."
            ),
            improvement=(
                "Keep subject on the learned third."
                if composition >= 78
                else f"Verplaats onderwerp naar {style_dna.subject_position if style_dna else 'rechter'} derde."
            ),
        )
    )
    axes.append(
        _axis(
            "negative_space",
            neg_score,
            why=(
                f"Negative space matches Style DNA ({learned_neg})."
                if neg_score >= 80
                else "Negative space does not match learned channel layout."
            ),
            improvement=(
                f"Keep clear {learned_neg} title column."
                if neg_score >= 80
                else f"Open {learned_neg or 'left'} negative space for title."
            ),
        )
    )
    axes.append(
        _axis(
            "subject_visibility",
            subject,
            why=(
                "Main subject is clearly specified."
                if subject >= 80
                else "Subject may be too small or centered."
            ),
            improvement=(
                "Keep hero scale large."
                if subject >= 80
                else "Vergroot hoofdonderwerp and push it off-center."
            ),
        )
    )

    # Lighting / contrast / color
    lighting = float(similarity.lighting)
    contrast = float(similarity.contrast)
    color = 70.0
    if plan.color_palette or (style_dna and style_dna.dominant_colors):
        color += 12.0
    if brief.brand.primary_color:
        color += 6.0
    axes.append(
        _axis(
            "lighting",
            lighting,
            why=(
                "Lighting matches reference atmosphere."
                if lighting >= 75
                else "Lighting is flatter than channel references."
            ),
            improvement=(
                "Keep cinematic rim/key light."
                if lighting >= 75
                else "Meer dramatisch licht — stronger key and rim."
            ),
        )
    )
    axes.append(
        _axis(
            "contrast",
            contrast,
            why=(
                "Contrast is reference-like."
                if contrast >= 75
                else "Contrast is too soft for CTR."
            ),
            improvement=(
                "Maintain high readable contrast."
                if contrast >= 75
                else "Increase contrast between subject and background."
            ),
        )
    )
    axes.append(
        _axis(
            "color_harmony",
            color,
            why=(
                "Brand/reference palette present."
                if color >= 80
                else "Color grading drifts from Brand Kit."
            ),
            improvement=(
                "Keep brand palette grading."
                if color >= 80
                else "Grade toward Brand Kit primary/secondary colors."
            ),
        )
    )

    # Visual focus
    focus = 72.0
    if plan.focal_point:
        focus += 8.0
    if plan.visual_hierarchy:
        focus += 6.0
    axes.append(
        _axis(
            "visual_focus",
            focus,
            why=(
                "Clear focal hierarchy."
                if focus >= 80
                else "Eye does not land on one dominant focus."
            ),
            improvement=(
                "Keep single focal peak."
                if focus >= 80
                else "Simplify midground and enlarge the focal subject."
            ),
        )
    )

    # Text layout / headline
    text_layout = 78.0 if composed else 55.0
    headline_size = 76.0 if composed else 55.0
    hierarchy = 74.0 if composed else 55.0
    if not words:
        text_layout -= 30.0
        headline_size -= 25.0
        hierarchy -= 20.0
    elif len(words) > max_words:
        text_layout -= 16.0
        headline_size -= 8.0
    if style_dna:
        if style_dna.text_max_lines >= 2:
            hierarchy += 8.0
        if style_dna.headline_scale >= 1.3:
            hierarchy += 6.0
            headline_size += 4.0
        if style_dna.text_coverage > 0.55:
            text_layout -= 12.0
            headline_size -= 10.0
    axes.append(
        _axis(
            "text_layout",
            text_layout,
            why=(
                "Title layout follows Style DNA."
                if text_layout >= 80
                else "Titel neemt teveel ruimte in of mist geleerde indeling."
            ),
            improvement=(
                "Keep learned line breaks and column."
                if text_layout >= 80
                else f"Verklein titel met 20%. Gebruik {style_dna.text_max_lines if style_dna else 3} regels."
            ),
        )
    )
    axes.append(
        _axis(
            "headline_size",
            headline_size,
            why=(
                "Headline size is CTR-readable without swallowing the frame."
                if headline_size >= 80
                else "Headline scale is off vs Style DNA coverage."
            ),
            improvement=(
                "Keep current headline scale."
                if headline_size >= 80
                else "Scale headline to learned text coverage (~"
                f"{int((style_dna.text_coverage if style_dna else 0.4) * 100)}%)."
            ),
        )
    )
    axes.append(
        _axis(
            "headline_hierarchy",
            hierarchy,
            why=(
                "Dominant word hierarchy matches channel DNA."
                if hierarchy >= 80
                else "All words share the same weight."
            ),
            improvement=(
                "Keep dominant middle/first word emphasis."
                if hierarchy >= 80
                else "Maak het middelste of eerste woord dominant (headline_scale)."
            ),
        )
    )

    # Logo
    logo_pos = 70.0
    logo_size = 70.0
    expected_pos = (
        style_dna.logo_position
        if style_dna
        else (plan.logo_area or brief.thumbnail.logo_position or "bottom_left")
    )
    placement = getattr(assets, "placement", None) if assets is not None else None
    if not brief.thumbnail.logo_visible:
        logo_pos = 88.0
        logo_size = 88.0
    elif not has_logo:
        logo_pos = 40.0
        logo_size = 40.0
    elif placement is not None:
        if str(placement.position) == str(expected_pos):
            logo_pos += 18.0
        else:
            logo_pos -= 16.0
        expected_scale = float(style_dna.logo_scale) if style_dna else 0.11
        delta = abs(float(placement.size) - expected_scale)
        if delta <= 0.03:
            logo_size += 18.0
        elif delta <= 0.06:
            logo_size += 6.0
        else:
            logo_size -= 14.0
    axes.append(
        _axis(
            "logo_position",
            logo_pos,
            why=(
                f"Logo matches learned position ({expected_pos})."
                if logo_pos >= 80
                else "Logo staat niet op de positie die geleerd is."
            ),
            improvement=(
                "Keep logo placement."
                if logo_pos >= 80
                else f"Plaats {expected_pos.replace('_', ' ')}. Gebruik schaal uit Thumbnail Style DNA."
            ),
        )
    )
    axes.append(
        _axis(
            "logo_size",
            logo_size,
            why=(
                "Logo scale matches Style DNA."
                if logo_size >= 80
                else "Logo scale drifts from learned DNA."
            ),
            improvement=(
                "Keep DNA logo scale."
                if logo_size >= 80
                else f"Set logo scale to {float(style_dna.logo_scale if style_dna else 0.11):.0%}."
            ),
        )
    )

    # Reference similarity
    ref = float(similarity.similarity_score)
    axes.append(
        _axis(
            "reference_similarity",
            ref,
            why=(
                f"Matches {similarity.reference_count} reference(s)."
                if ref >= 75
                else "Looks unlike uploaded channel references."
            ),
            improvement=(
                "Keep reference lighting/composition."
                if ref >= 75
                else "Match reference lighting, contrast, and subject bias more closely."
            ),
        )
    )

    # Emotion / professional / impact
    emotion_score = 68.0
    if plan.emotion:
        emotion_score += 12.0
    if style_dna and style_dna.mood and style_dna.mood.casefold() in emotion:
        emotion_score += 10.0
    pro = (
        0.35 * brand
        + 0.25 * composition
        + 0.2 * text_layout
        + 0.2 * float(similarity.atmosphere)
    )
    impact = (
        0.3 * ctr
        + 0.25 * curiosity
        + 0.2 * float(similarity.contrast)
        + 0.15 * subject
        + 0.1 * mystery
    )
    axes.append(
        _axis(
            "emotion",
            emotion_score,
            why=(
                "Emotion is explicit and on-brand."
                if emotion_score >= 80
                else "Emotion is vague."
            ),
            improvement=(
                "Keep the planned emotion."
                if emotion_score >= 80
                else f"Push {plan.emotion or brief.thumbnail.emotion or 'curiosity'} harder."
            ),
        )
    )
    axes.append(
        _axis(
            "professional_appearance",
            pro,
            why=(
                "Looks like a finished YouTube thumbnail."
                if pro >= 80
                else "Still reads as an unfinished AI still."
            ),
            improvement=(
                "Maintain brand + layout polish."
                if pro >= 80
                else "Tighten logo, title hierarchy, and reference match."
            ),
        )
    )
    axes.append(
        _axis(
            "overall_impact",
            impact,
            why=(
                "Strong stop-scroll impact."
                if impact >= 80
                else "Impact is average — not yet click-stopping."
            ),
            improvement=(
                "Keep high-impact cues."
                if impact >= 80
                else "Increase subject scale, contrast, and curiosity beat."
            ),
        )
    )

    # Ensure every declared axis exists
    present = {a.axis for a in axes}
    for name in CRITIC_AXES:
        if name not in present:
            axes.append(_axis(name, 70.0, why="Baseline", improvement="Maintain quality."))
    return axes


def _axis(name: str, score: float, *, why: str, improvement: str) -> AxisCritique:
    return AxisCritique(
        axis=name,
        score=round(max(0.0, min(100.0, float(score))), 2),
        why=why,
        improvement=improvement,
    )
