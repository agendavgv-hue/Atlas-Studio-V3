"""SceneDirectorService — choose the highest-curiosity story scene before prompts."""

from __future__ import annotations

from pathlib import Path

from app.creative.director.analysis import CreativeDirectorAnalysis
from app.creative.engine.brief import CreativeBrief
from app.creative.engine.style_profile import StyleProfile
from app.providers.base import TextProvider
from app.thumbnail.concepts.models import ThumbnailConceptIdea
from app.thumbnail.scene_director.invent import MIN_SCENES, SceneInventor
from app.thumbnail.scene_director.models import SceneBlueprint, SceneCandidate
from app.thumbnail.scene_director.scorer import SceneScorer
from app.thumbnail.scene_director.store import write_scene_blueprint


class SceneDirectorService:
    """Think like a YouTube thumbnail designer: pick the scene, not the pretty picture."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self._inventor = SceneInventor(text_provider)
        self._scorer = SceneScorer()

    def direct(
        self,
        brief: CreativeBrief,
        *,
        script_text: str = "",
        sheet_text: str = "",
        topic: str = "",
        analysis: CreativeDirectorAnalysis | None = None,
        best_concept: ThumbnailConceptIdea | None = None,
        thumbnail_profile: StyleProfile | None = None,
        project_dir: Path | None = None,
        min_scenes: int = MIN_SCENES,
    ) -> SceneBlueprint:
        scenes = self._inventor.invent(
            brief=brief,
            script_text=script_text,
            sheet_text=sheet_text,
            topic=topic,
            analysis=analysis,
            best_concept=best_concept,
            thumbnail_profile=thumbnail_profile,
            min_scenes=min_scenes,
        )
        for scene in scenes:
            scene.scores = self._scorer.score(
                scene, brief=brief, thumbnail_profile=thumbnail_profile
            )
            self._enforce_minimums(scene)

        ranked = sorted(scenes, key=lambda s: s.scores.overall, reverse=True)
        winner = ranked[0]
        for scene in ranked:
            if self._as_blueprint(scene, brief, topic, ranked, "").meets_minimum_rules():
                winner = scene
                break

        reason = _selection_reason(winner, ranked, analysis)
        blueprint = self._as_blueprint(winner, brief, topic, scenes, reason)
        if not blueprint.meets_minimum_rules():
            blueprint = self._repair_blueprint(blueprint, brief, topic)

        if project_dir is not None:
            write_scene_blueprint(project_dir, blueprint)
        return blueprint

    def _as_blueprint(
        self,
        winner: SceneCandidate,
        brief: CreativeBrief,
        topic: str,
        candidates: list[SceneCandidate],
        reason: str,
    ) -> SceneBlueprint:
        return SceneBlueprint(
            main_subject=winner.main_subject,
            secondary_subject=winner.secondary_subject,
            background=winner.background,
            foreground=winner.foreground,
            lighting=winner.lighting or "golden cinematic",
            weather=winner.weather,
            composition="rule_of_thirds",
            negative_space=winner.negative_space or "left",
            emotion=winner.emotion or brief.thumbnail.emotion or "curiosity",
            story=winner.story,
            camera=winner.camera,
            lens=winner.lens,
            depth=winner.depth,
            atmosphere=winner.atmosphere,
            color_palette=list(winner.color_palette)
            or [
                c
                for c in (
                    brief.brand.primary_color,
                    brief.brand.secondary_color,
                    brief.brand.accent_color,
                )
                if c
            ],
            visual_focus=winner.visual_focus,
            title=winner.title,
            selected_scene_id=winner.id,
            selection_reason=reason,
            candidates=list(candidates),
            channel_name=brief.channel_name,
            project_topic=(topic or brief.project.topic or brief.project.idea).strip(),
            extras={
                "scores": winner.scores.to_dict(),
                "meets_minimum_rules": True,
            },
        )

    def _repair_blueprint(
        self, blueprint: SceneBlueprint, brief: CreativeBrief, topic: str
    ) -> SceneBlueprint:
        mystery = brief.project.primary_subject or topic or "mysterious artifact"
        if not blueprint.main_subject:
            blueprint.main_subject = "explorer silhouette"
        if not blueprint.secondary_subject:
            blueprint.secondary_subject = mystery
        if not blueprint.background:
            blueprint.background = brief.project.primary_location or "epic storm horizon"
        if not blueprint.emotion:
            blueprint.emotion = brief.thumbnail.emotion or "curiosity"
        if len(blueprint.story.split()) < 8:
            blueprint.story = (
                f"{blueprint.main_subject} discovers that {blueprint.secondary_subject} "
                f"behaves impossibly while {blueprint.background} unfolds behind them."
            )
        blueprint.extras["repaired"] = True
        blueprint.selection_reason = (
            f"{blueprint.selection_reason} Repaired to meet storytelling minimums."
        ).strip()
        return blueprint

    @staticmethod
    def _enforce_minimums(scene: SceneCandidate) -> None:
        if not scene.main_subject:
            scene.main_subject = "explorer"
            scene.notes.append("filled missing main subject")
        if not scene.secondary_subject:
            scene.secondary_subject = "mysterious object"
            scene.notes.append("filled missing mysterious object")
        if not scene.background:
            scene.background = "epic atmospheric background"
            scene.notes.append("filled missing background")
        if len(scene.story.split()) < 8:
            scene.story = (
                f"{scene.main_subject} confronts {scene.secondary_subject} "
                f"as {scene.background} reveals an unanswered question."
            )
            scene.notes.append("expanded thin story into narrative beat")


def _selection_reason(
    winner: SceneCandidate,
    ranked: list[SceneCandidate],
    analysis: CreativeDirectorAnalysis | None,
) -> str:
    axes = [
        ("curiosity", winner.scores.curiosity),
        ("CTR", winner.scores.ctr_potential),
        ("story", winner.scores.story),
        ("visual", winner.scores.visual_strength),
    ]
    top = ", ".join(f"{n} {v:.0f}" for n, v in sorted(axes, key=lambda kv: -kv[1])[:3])
    runner = ranked[1] if len(ranked) > 1 else None
    margin = ""
    if runner is not None:
        margin = (
            f" Beat scene {runner.id} (“{runner.title}”) by "
            f"{winner.scores.overall - runner.scores.overall:.1f}."
        )
    director_note = ""
    if analysis and analysis.greatest_mystery:
        director_note = f" Aligns with Creative Director mystery: {analysis.greatest_mystery}."
    return (
        f"Scene {winner.id} “{winner.title}” won with overall "
        f"{winner.scores.overall:.1f}/100 ({top}).{margin}{director_note} "
        f"Story locked: {winner.story}"
    ).strip()
