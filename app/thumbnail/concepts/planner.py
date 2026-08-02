"""ThumbnailConceptPlanner — invent → score → choose (no prompts, no images)."""

from __future__ import annotations

from pathlib import Path

from app.creative.engine.brief import CreativeBrief
from app.creative.engine.style_profile import StyleProfile
from app.providers.base import TextProvider
from app.thumbnail.concepts.invent import MIN_CONCEPTS, ConceptInventor
from app.thumbnail.concepts.models import ConceptBoard, ThumbnailConceptIdea
from app.thumbnail.concepts.scorer import ConceptScorer
from app.thumbnail.concepts.store import write_concept_board


class ThumbnailConceptPlanner:
    """Professional think-step before any thumbnail prompt is written."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self._inventor = ConceptInventor(text_provider)
        self._scorer = ConceptScorer()

    def plan(
        self,
        brief: CreativeBrief,
        *,
        script_text: str = "",
        topic: str = "",
        thumbnail_profile: StyleProfile | None = None,
        min_concepts: int = MIN_CONCEPTS,
        project_dir: Path | None = None,
    ) -> ConceptBoard:
        concepts, scene, click_reason = self._inventor.invent(
            brief=brief,
            script_text=script_text,
            topic=topic,
            thumbnail_profile=thumbnail_profile,
            min_concepts=min_concepts,
        )
        if len(concepts) < min_concepts:
            # Guaranteed floor via heuristic padding.
            extra, _, _ = ConceptInventor(None).invent(
                brief=brief,
                script_text=script_text,
                topic=topic or scene,
                thumbnail_profile=thumbnail_profile,
                min_concepts=min_concepts,
            )
            used_titles = {c.title.casefold() for c in concepts}
            for item in extra:
                if item.title.casefold() in used_titles:
                    continue
                item.id = len(concepts) + 1
                concepts.append(item)
                if len(concepts) >= min_concepts:
                    break

        sibling_ideas = [c.summary_line() for c in concepts]
        for concept in concepts:
            concept.scores = self._scorer.score(
                concept,
                brief=brief,
                thumbnail_profile=thumbnail_profile,
                sibling_ideas=sibling_ideas,
            )

        ranked = sorted(concepts, key=lambda c: c.scores.overall, reverse=True)
        winner = ranked[0]
        reason = _selection_reason(winner, ranked, brief, thumbnail_profile)

        personality_focus = [
            k
            for k, v in sorted(
                (brief.personality.traits or {}).items(), key=lambda kv: -kv[1]
            )
            if v >= 70
        ][:8]

        reference_analysis = _reference_analysis_dict(thumbnail_profile)

        board = ConceptBoard(
            project_topic=(
                topic
                or brief.project.topic
                or brief.project.idea
                or brief.channel_name
            ).strip(),
            channel_name=brief.channel_name,
            concepts=concepts,
            selected_id=winner.id,
            selected_reason=reason,
            reference_analysis=reference_analysis,
            personality_focus=personality_focus,
            selected_scene=scene,
            click_value_reason=click_reason or reason,
            extras={
                "min_concepts": min_concepts,
                "concept_count": len(concepts),
                "winner_overall": winner.scores.overall,
            },
        )
        if project_dir is not None:
            write_concept_board(project_dir, board)
        return board


def _selection_reason(
    winner: ThumbnailConceptIdea,
    ranked: list[ThumbnailConceptIdea],
    brief: CreativeBrief,
    thumbnail_profile: StyleProfile | None,
) -> str:
    scores = winner.scores
    axes = [
        ("curiosity", scores.curiosity),
        ("mystery", scores.mystery),
        ("visual_impact", scores.visual_impact),
        ("ctr_potential", scores.ctr_potential),
        ("brand_match", scores.brand_match),
        ("thumbnail_strength", scores.thumbnail_strength),
    ]
    top_axes = ", ".join(
        f"{name} {value:.0f}"
        for name, value in sorted(axes, key=lambda kv: -kv[1])[:3]
    )
    runner = ranked[1] if len(ranked) > 1 else None
    margin = ""
    if runner is not None:
        margin = (
            f" Beat concept {runner.id} (“{runner.title}”) by "
            f"{scores.overall - runner.scores.overall:.1f} points."
        )
    ref_note = ""
    if thumbnail_profile and thumbnail_profile.reference_count > 0:
        ref_note = (
            f" Aligned with reference style "
            f"({thumbnail_profile.negative_space} negative space, "
            f"{thumbnail_profile.mood} mood)."
        )
    traits = [
        k
        for k, v in sorted((brief.personality.traits or {}).items(), key=lambda kv: -kv[1])
        if v >= 70
    ][:3]
    trait_note = f" Matches channel personality ({', '.join(traits)})." if traits else ""
    return (
        f"Concept {winner.id} “{winner.title}” won with overall "
        f"{scores.overall:.1f}/100 ({top_axes}).{margin}{trait_note}{ref_note} "
        f"Elements locked: {', '.join(winner.elements[:5]) or winner.summary_line()}."
    ).strip()


def _reference_analysis_dict(profile: StyleProfile | None) -> dict:
    if profile is None:
        return {"reference_count": 0}
    return {
        "reference_count": profile.reference_count,
        "dominant_colors": list(profile.dominant_colors),
        "subject_bias": profile.subject_bias,
        "negative_space": profile.negative_space,
        "text_position": profile.text_position,
        "camera_angle": profile.camera_angle,
        "contrast": profile.contrast,
        "brightness": profile.brightness,
        "color_temperature": profile.color_temperature,
        "atmosphere": profile.atmosphere,
        "mood": profile.mood,
        "logo_bias": profile.logo_bias,
        "average_words": profile.average_words,
        "realism": profile.realism,
    }
