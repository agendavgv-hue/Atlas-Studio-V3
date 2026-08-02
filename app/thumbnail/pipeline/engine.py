"""Thumbnail Pipeline V3 engine — definitive production orchestrator."""

from __future__ import annotations

import copy
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.providers.base import TextProvider
from app.providers.errors import ProviderError
from app.providers.image_base import ImageProvider
from app.thumbnail.generator import ThumbnailGenerator
from app.thumbnail.naming import (
    THUMBNAIL_BASENAME,
    THUMBNAIL_CONCEPTS_BASENAME,
    THUMBNAIL_FOLDER,
    THUMBNAIL_PROMPT_BASENAME,
    THUMBNAIL_TITLE_BASENAME,
    VARIANT_BASENAMES,
    resolve_thumbnail_dir,
    thumbnail_path,
    thumbnail_prompt_path,
    thumbnail_title_path,
    thumbnail_variant_path,
)
from app.thumbnail.pipeline.brand_composer import BrandComposer
from app.thumbnail.pipeline.critic_scores import DEFAULT_CRITIC_THRESHOLD
from app.thumbnail.pipeline.debug_report import build_debug_report, write_thumbnail_debug
from app.thumbnail.pipeline.plan import (
    ThumbnailCompositionPlanner,
    save_thumbnail_plan,
)
from app.thumbnail.pipeline.prompt_builder import build_pipeline_prompt_plans
from app.thumbnail.pipeline.reference_compare import compare_to_references
from app.thumbnail.settings import ThumbnailSettings
from app.thumbnail.scene_director import SceneDirectorService
from app.thumbnail.scene_director.store import SCENE_BLUEPRINT_BASENAME
from app.thumbnail.critic_engine.improve import ImproveEngine
from app.thumbnail.critic_engine.learning import CriticLearningStore
from app.thumbnail.critic_engine.models import CriticGroupScores, ReviewVersion, ThumbnailReviewBoard
from app.thumbnail.critic_engine.service import ThumbnailCriticService
from app.thumbnail.critic_engine.compat import report_to_pipeline_scores
from app.thumbnail.critic_engine.store import (
    THUMBNAIL_REVIEW_BASENAME,
    write_critic_report,
    write_review_board,
)
from app.thumbnail.design_engine.service import DesignEngineService
from app.thumbnail.design_engine.store import DESIGN_REVIEW_BASENAME

ProgressCallback = Callable[[str, str], None]
CancelCallback = Callable[[], bool]

THUMBNAIL_PLAN_BASENAME = "thumbnail_plan.json"
THUMBNAIL_DEBUG_BASENAME = "thumbnail_debug.json"
FINAL_PROMPT_BASENAME = "final_prompt.txt"


@dataclass
class PipelineAttemptRecord:
    attempt: int
    critic_overall: float
    similarity: float
    approved: bool
    adjustments: list[str]
    primary_variant: str


class ThumbnailPipelineEngine:
    """
    Creative Director → Concept Planner → Scene Director → Prompt Builder →
    AI → Brand Composer → Critic → Export
    """

    def __init__(
        self,
        settings: ThumbnailSettings,
        *,
        image_provider: ImageProvider | None,
        text_provider: TextProvider | None,
        data_root: Path | None,
        on_progress: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
        critic_threshold: int = DEFAULT_CRITIC_THRESHOLD,
        app_config: Any | None = None,
    ) -> None:
        self._settings = settings
        self._data_root = Path(data_root) if data_root is not None else None
        self._on_progress = on_progress
        self._should_cancel = should_cancel
        self._app_config = app_config
        self._image_provider = image_provider
        self._text_provider = text_provider
        self._generator = ThumbnailGenerator(image_provider)
        self._plan_builder = ThumbnailCompositionPlanner()
        self._critic = ThumbnailCriticService(threshold=critic_threshold)
        self._improve = ImproveEngine()
        self._design = DesignEngineService()
        self._brand: BrandComposer | None = (
            BrandComposer(self._data_root) if self._data_root is not None else None
        )
        self._orchestrator = None
        if app_config is not None:
            from app.ai.orchestrator import AIOrchestratorService

            self._orchestrator = AIOrchestratorService(app_config)
            # Image Generator role → Forge (unless test override).
            if image_provider is None:
                try:
                    self._image_provider = self._orchestrator.image_for()
                    self._generator = ThumbnailGenerator(self._image_provider)
                except Exception:  # noqa: BLE001
                    pass


    def run(
        self,
        context: PipelineContext,
        *,
        script_text: str,
        sheet_text: str = "",
    ) -> PipelineResult:
        started = time.perf_counter()
        if self._data_root is None:
            return self._fail("Thumbnail Pipeline V3 requires a data root.", started)
        if self._should_cancel and self._should_cancel():
            return PipelineResult.cancelled()

        # --- Creative Director ---
        self._emit("Creative Director loading Channel Studio", "creative_director")
        try:
            from app.creative.engine import CreativeDirectorEngine
            from app.creative.engine.style_profile_service import StyleProfileService
            from app.channels.studio.service import ChannelStudioService
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Creative Director unavailable: {exc}", started)

        engine = CreativeDirectorEngine(self._data_root)
        brief = getattr(context, "creative_brief", None)
        if brief is None:
            brief = engine.build_brief(
                context.channel_name,
                project=context.project,
                script_text=script_text,
                sheet_text=sheet_text,
            )
            object.__setattr__(context, "creative_brief", brief)
        else:
            engine.enrich_project(
                brief, script_text=script_text, sheet_text=sheet_text
            )

        profiles = StyleProfileService(self._data_root)
        thumb_profile = profiles.ensure_thumbnail_profile(context.channel_name)
        image_profile = profiles.ensure_image_profile(context.channel_name)
        studio = ChannelStudioService(self._data_root)
        ref_paths = studio.list_references(context.channel_name, "thumbnails")
        style_dna = None
        try:
            from app.thumbnail.style_dna.service import ThumbnailStyleDNAService

            style_dna = ThumbnailStyleDNAService(self._data_root).load(
                context.channel_name
            )
        except Exception:  # noqa: BLE001
            style_dna = None

        engine.write_report(
            context.project_dir,
            brief,
            domain="thumbnail",
            master_prompt_text="",
            thumbnail_profile_loaded=True,
            image_profile_loaded=image_profile is not None,
            notes=["Thumbnail Pipeline V3 + Scene Director"],
        )

        # --- AI Orchestrator → Creative Director (think before generate) ---
        if self._should_cancel and self._should_cancel():
            return PipelineResult.cancelled()
        self._emit("Creative Director analyzing project", "creative_director_think")
        topic = (
            getattr(context.project, "idea", "")
            or getattr(context.project, "name", "")
            or brief.project.idea
            or brief.project.topic
            or context.channel_name
        )
        cd_report = None
        best_concept = None
        concept_board = None
        analysis_block = ""
        analysis = None
        if self._orchestrator is not None:
            from app.creative.director import CreativeDirector
            from app.ai.orchestrator import ResolvedAI
            from app.ai.roles import AIRole

            # Test overrides: force Creative Director onto the injected text provider.
            if self._text_provider is not None:
                forced = self._text_provider

                def _resolve_text(role, _forced=forced):
                    role_enum = role if isinstance(role, AIRole) else AIRole(str(role))
                    return ResolvedAI(
                        role=role_enum,
                        provider_id=getattr(_forced, "provider_id", "override"),
                        model="override",
                        provider=_forced,
                        used_fallback=False,
                    )

                self._orchestrator.resolve_text = _resolve_text  # type: ignore[method-assign]

            director = CreativeDirector(self._orchestrator)
            cd_report = director.direct_thumbnail(
                brief,
                script_text=script_text,
                sheet_text=sheet_text,
                topic=str(topic),
                thumbnail_profile=thumb_profile,
                project_dir=context.project_dir,
            )
            concept_board = cd_report.concepts
            best_concept = concept_board.chosen if concept_board else None
            analysis = cd_report.analysis
            analysis_block = cd_report.analysis.prompt_block()
            self._emit(
                f"Creative Director via {cd_report.provider_id}"
                + (" (fallback)" if cd_report.used_fallback else ""),
                "creative_director_ready",
            )
        if best_concept is None:
            from app.thumbnail.concepts.planner import ThumbnailConceptPlanner

            planner = ThumbnailConceptPlanner(self._text_provider)
            concept_board = planner.plan(
                brief,
                script_text=script_text,
                topic=str(topic),
                thumbnail_profile=thumb_profile,
                project_dir=context.project_dir,
            )
            best_concept = concept_board.chosen

        hero = best_concept.hero_subject or best_concept.foreground or topic
        hook = _normalize_hook(
            best_concept.hook or best_concept.title,
            brief.thumbnail.max_words,
        )
        strategy = None
        self._emit(
            f"Best concept #{best_concept.id} “{best_concept.title}” "
            f"({best_concept.scores.overall:.0f}/100)",
            "concept_selected",
        )

        # --- Scene Director (always before prompts) ---
        if self._should_cancel and self._should_cancel():
            return PipelineResult.cancelled()
        self._emit("Scene Director choosing the highest-curiosity scene", "scene_director")
        scene_director = SceneDirectorService(self._text_provider)
        scene_blueprint = scene_director.direct(
            brief,
            script_text=script_text,
            sheet_text=sheet_text,
            topic=str(topic),
            analysis=analysis,
            best_concept=best_concept,
            thumbnail_profile=thumb_profile,
            project_dir=context.project_dir,
        )
        hero = scene_blueprint.main_subject or hero
        self._emit(
            f"Scene #{scene_blueprint.selected_scene_id} “{scene_blueprint.title}” locked",
            "scene_selected",
        )

        # --- Thumbnail composition plan from Scene Blueprint ---
        self._emit("Building Thumbnail Plan from Scene Blueprint", "planner")
        plan = self._plan_builder.plan(
            brief,
            hero_subject=str(hero),
            hook=str(hook),
            location=brief.project.primary_location,
            thumbnail_profile=thumb_profile,
            best_concept=best_concept,
            scene_blueprint=scene_blueprint,
        )
        if analysis_block:
            plan.extras["creative_director_analysis"] = analysis_block
        plan.extras["scene_blueprint_story"] = scene_blueprint.story
        plan_path = resolve_thumbnail_dir(context.project_dir) / THUMBNAIL_PLAN_BASENAME
        save_thumbnail_plan(plan_path, plan)

        # --- Brand assets ---
        assert self._brand is not None
        assets = self._brand.resolve_assets(
            brief, plan, thumbnail_profile=thumb_profile, style_dna=style_dna
        )

        max_attempts = max(1, min(3, int(getattr(self._settings, "max_quality_attempts", 3) or 3)))
        attempts: list[dict[str, Any]] = []
        review_versions: list[ReviewVersion] = []
        best: dict[str, Any] | None = None
        critic_notes = ""
        improve_plan = None
        learning_hints = ""
        try:
            memory = CriticLearningStore(self._data_root).load(context.channel_name)
            learning_hints = memory.prompt_hints()
        except Exception:  # noqa: BLE001
            learning_hints = ""

        for attempt in range(1, max_attempts + 1):
            if self._should_cancel and self._should_cancel():
                return PipelineResult.cancelled()

            self._emit(f"Pipeline attempt {attempt}/{max_attempts}", f"attempt_{attempt}")

            if attempt > 1 and improve_plan is not None:
                self._emit("Improve Engine applying weak-axis fixes", "improve")
                plan = self._plan_builder.plan(
                    brief,
                    hero_subject=str(hero),
                    hook=str(hook),
                    location=brief.project.primary_location,
                    thumbnail_profile=thumb_profile,
                    critic_feedback=improve_plan.prompt_block(),
                    best_concept=best_concept,
                    scene_blueprint=scene_blueprint,
                )
                save_thumbnail_plan(plan_path, plan)
                assets = self._improve.apply_compose_adjustments(
                    assets, improve_plan, style_dna=style_dna
                )

            # --- Image Prompt Builder (Scene Blueprint + Improve Plan) ---
            self._emit("Building image prompts from Scene Blueprint", "prompts")
            plans = build_pipeline_prompt_plans(
                brief,
                plan,
                thumbnail_profile=thumb_profile,
                image_profile=image_profile,
                critic_notes=critic_notes,
                best_concept=best_concept,
                scene_blueprint=scene_blueprint,
                style_dna=style_dna,
                improve_plan=improve_plan,
            )
            primary_prompt = plans[0].prompt if plans else ""
            if analysis_block and "CREATIVE DIRECTOR ANALYSIS" not in primary_prompt:
                primary_prompt = f"{analysis_block}\n\n{primary_prompt}"
            if learning_hints and "CRITIC LEARNING" not in primary_prompt:
                primary_prompt = f"{learning_hints}\n\n{primary_prompt}"
            if analysis_block or learning_hints:
                from app.thumbnail.prompt_builder import ThumbnailPromptPlan

                plans[0] = ThumbnailPromptPlan(
                    variant_id=plans[0].variant_id,
                    variant_key=plans[0].variant_key,
                    variant_label=plans[0].variant_label,
                    prompt=primary_prompt,
                    negative_prompt=plans[0].negative_prompt,
                )

            # --- AI Image Generation ---
            try:
                variants, snapshots = self._generate_variants(plans, attempt=attempt)
            except ProviderError as exc:
                return self._fail(str(exc), started)
            except _Cancelled:
                return PipelineResult.cancelled()

            primary_id = str(getattr(self._settings, "primary_variant", "A") or "A").upper()
            by_id = {vid.upper(): png for vid, png in variants}
            raw_primary = by_id.get(primary_id) or variants[0][1]

            # --- Design Engine (AI illustration only → Atlas designs) ---
            self._emit("Design Engine analyzing illustration + layouts", "design_engine")
            design_result = self._design.design(
                raw_primary,
                hook=hook,
                assets=assets,
                style_dna=style_dna,
                channel_name=context.channel_name,
                project_name=str(getattr(context.project, "name", "") or ""),
                project_dir=context.project_dir,
            )
            composed = design_result.image_png
            self._emit(
                f"Design winner Layout {design_result.winner.id} "
                f"({design_result.winner.scores.overall:.0f}/100)",
                "design_selected",
            )

            # Persist attempt preview for Thumbnail Review
            attempt_name = f"thumbnail_attempt_{attempt}.png"
            (resolve_thumbnail_dir(context.project_dir) / attempt_name).write_bytes(composed)

            # --- Reference Comparison ---
            self._emit("Comparing to thumbnail references", "reference_compare")
            similarity = compare_to_references(
                composed,
                reference_paths=ref_paths,
                thumbnail_profile=thumb_profile,
            )

            # --- Thumbnail Critic ---
            self._emit("Thumbnail Critic scoring", "critic")
            report = self._critic.evaluate(
                brief=brief,
                plan=plan,
                similarity=similarity,
                hook=hook,
                prompt=primary_prompt,
                has_logo=assets.logo_path is not None and assets.logo_path.is_file(),
                has_frame=assets.frame_path is not None
                and assets.frame_path.is_file(),
                composed=True,
                scene_blueprint=scene_blueprint,
                style_dna=style_dna,
                assets=assets,
                attempt=attempt,
            )
            critic = report_to_pipeline_scores(report)
            next_improve = None
            if not report.approved:
                next_improve = self._improve.build_plan(report, style_dna=style_dna)

            review_versions.append(
                ReviewVersion(
                    attempt=attempt,
                    overall=report.overall,
                    approved=report.approved,
                    image_relpath=f"{THUMBNAIL_FOLDER}/{attempt_name}",
                    report=report,
                    improve_plan=next_improve,
                    prompt=primary_prompt,
                )
            )
            record = {
                "attempt": attempt,
                "critic_overall": critic.overall,
                "similarity": similarity.similarity_score,
                "approved": critic.approved,
                "adjustments": list(critic.adjustments),
                "primary_variant": primary_id,
                "critic_axes": {
                    "brand_consistency": critic.brand_consistency,
                    "reference_similarity": critic.reference_similarity,
                    "readability": critic.readability,
                    "composition": critic.composition,
                    "ctr_potential": critic.ctr_potential,
                    "mystery": critic.mystery,
                    "visual_impact": critic.visual_impact,
                },
                "variants": variants,
                "snapshots": snapshots,
                "composed": composed,
                "primary_prompt": primary_prompt,
                "critic": critic,
                "critic_report": report,
                "similarity_report": similarity,
                "plan": plan,
                "improve_plan": next_improve,
                "design_board": design_result.board,
                "design_winner_id": design_result.winner.id,
                "design_winner_score": design_result.winner.scores.overall,
                "design_winner_why": design_result.board.winner_why,
            }
            attempts.append(
                {
                    "attempt": attempt,
                    "critic_overall": critic.overall,
                    "similarity": similarity.similarity_score,
                    "approved": critic.approved,
                    "adjustments": list(critic.adjustments),
                    "groups": report.groups.to_dict(),
                }
            )
            if best is None or critic.overall > float(best["critic_overall"]):
                best = record

            self._emit(
                f"Critic {critic.overall:.1f}/{self._critic.threshold}"
                + (" approved" if critic.approved else " — improving"),
                "critic_score",
            )

            if critic.approved:
                break
            improve_plan = next_improve
            critic_notes = (
                self._improve.critic_notes(improve_plan)
                if improve_plan is not None
                else "; ".join(critic.notes)
            )

        if best is None:
            return self._fail("Thumbnail Pipeline produced no candidates.", started)

        # --- Export best attempt ---
        self._emit("Exporting thumbnail package", "export")
        try:
            self._export(
                context.project_dir,
                hook=hook,
                variants=best["variants"],
                composed_primary=best["composed"],
                primary_prompt=best["primary_prompt"],
                plan=best["plan"],
            )
        except OSError as exc:
            return self._fail(f"Thumbnail export failed: {exc}", started)

        debug = build_debug_report(
            brief=brief,
            plan=best["plan"],
            prompt=best["primary_prompt"],
            similarity=best["similarity_report"],
            critic=best["critic"],
            attempts=attempts,
        )
        debug.extras["strategy"] = {
            "emotion": getattr(strategy, "emotion", "") or best_concept.emotion,
            "click_reason": getattr(strategy, "click_reason", "")
            or (concept_board.selected_reason if concept_board else ""),
        }
        debug.extras["best_concept"] = best_concept.to_dict()
        debug.extras["concept_count"] = (
            len(concept_board.concepts) if concept_board else 0
        )
        debug.extras["scene_blueprint"] = scene_blueprint.to_dict()
        debug.extras["scene_selection_reason"] = scene_blueprint.selection_reason
        if style_dna is not None:
            debug.extras["style_dna"] = style_dna.to_dict()
            debug.extras["Style DNA"] = {
                row[0]: row[1] for row in style_dna.debug_rows()
            }
        design_board = best.get("design_board")
        if design_board is not None:
            debug.extras["design_engine"] = {
                "winner_id": best.get("design_winner_id"),
                "winner_score": best.get("design_winner_score"),
                "winner_why": best.get("design_winner_why"),
                "layout_count": len(design_board.layouts),
            }
            from app.thumbnail.design_engine.store import write_design_review

            write_design_review(context.project_dir, design_board)
        best_report = best.get("critic_report")
        if best_report is not None:
            debug.extras["critic_report"] = best_report.to_dict()
            debug.extras["Critic Groups"] = best_report.groups.to_dict()
        debug_path = resolve_thumbnail_dir(context.project_dir) / THUMBNAIL_DEBUG_BASENAME
        write_thumbnail_debug(debug_path, debug)

        # Thumbnail Review board + critic learning
        winner_attempt = int(best["attempt"])
        board = ThumbnailReviewBoard(
            channel_name=brief.channel_name,
            project_name=str(getattr(context.project, "name", "") or ""),
            winner_attempt=winner_attempt,
            winner_score=float(best["critic_overall"]),
            versions=review_versions,
            groups=(
                best_report.groups
                if best_report is not None
                else (
                    review_versions[-1].report.groups
                    if review_versions and review_versions[-1].report is not None
                    else CriticGroupScores()
                )
            ),
            threshold=self._critic.threshold,
        )
        write_review_board(context.project_dir, board)
        if best_report is not None:
            write_critic_report(context.project_dir, best_report)
            try:
                CriticLearningStore(self._data_root).record_win(
                    context.channel_name, best_report
                )
            except Exception:  # noqa: BLE001
                pass

        # Refresh CD report with final prompt length
        engine.write_report(
            context.project_dir,
            brief,
            domain="thumbnail",
            master_prompt_text=best["primary_prompt"],
            thumbnail_profile_loaded=True,
            image_profile_loaded=True,
            notes=[
                "Thumbnail Pipeline V3",
                f"Final critic {best['critic'].overall}",
                f"Similarity {best['similarity_report'].similarity_score}",
            ],
        )

        artifacts = [
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_CONCEPTS_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{SCENE_BLUEPRINT_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_PLAN_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_DEBUG_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_REVIEW_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{DESIGN_REVIEW_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_PROMPT_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_TITLE_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_BASENAME}",
        ]
        for vid, _ in best["variants"]:
            name = VARIANT_BASENAMES.get(vid)
            if name:
                artifacts.append(f"{THUMBNAIL_FOLDER}/{name}")

        if not best["critic"].approved:
            return PipelineResult.warning(
                f"Pipeline V3 best effort ({best['critic'].overall:.0f}/100, "
                f"need ≥ {self._critic.threshold}) · {brief.channel_name} · "
                f"hook “{hook}”",
                errors=[
                    f"Critic below threshold after {max_attempts} attempts "
                    f"(best {best['critic'].overall})"
                ],
                artifacts=artifacts,
                execution_time_ms=int((time.perf_counter() - started) * 1000),
            )

        return PipelineResult.success(
            f"Pipeline V3 approved ({best['critic'].overall:.0f}/100) · "
            f"{brief.channel_name} · scene “{scene_blueprint.title}” · hook “{hook}”",
            artifacts=artifacts,
            execution_time_ms=int((time.perf_counter() - started) * 1000),
        )

    def _generate_variants(self, plans, *, attempt: int):
        attempt_settings = copy.copy(self._settings)
        base_seed = int(
            getattr(self._settings, "seed", -1)
            if getattr(self._settings, "seed", -1) is not None
            else -1
        )
        if base_seed < 0:
            attempt_settings.seed = 1000 + attempt
        else:
            attempt_settings.seed = base_seed + (attempt - 1)

        variants: list[tuple[str, bytes]] = []
        snapshots: list[dict] = []
        for plan in plans:
            if self._should_cancel and self._should_cancel():
                raise _Cancelled()
            self._emit(
                f"Generating variant {plan.variant_id} ({plan.variant_label})",
                f"variant_{plan.variant_id.lower()}",
            )
            generated = self._generator.generate_variant(plan, settings=attempt_settings)
            variants.append((plan.variant_id, generated.image_png))
            snapshots.append(
                {
                    "variant_id": plan.variant_id,
                    "variant_key": plan.variant_key,
                    "prompt": plan.prompt,
                    "negative_prompt": plan.negative_prompt,
                    "seed": generated.seed,
                    "model": generated.model,
                    "provider_id": generated.provider_id,
                    "width": generated.width,
                    "height": generated.height,
                }
            )
        return variants, snapshots

    def _export(
        self,
        project_dir: Path,
        *,
        hook: str,
        variants: list[tuple[str, bytes]],
        composed_primary: bytes,
        primary_prompt: str,
        plan,
    ) -> None:
        out = resolve_thumbnail_dir(project_dir)
        for variant_id, image_png in variants:
            thumbnail_variant_path(project_dir, variant_id).write_bytes(image_png)
        thumbnail_path(project_dir).write_bytes(composed_primary)
        thumbnail_title_path(project_dir).write_text(hook.strip() + "\n", encoding="utf-8")
        thumbnail_prompt_path(project_dir).write_text(
            primary_prompt.strip() + "\n", encoding="utf-8"
        )
        (out / FINAL_PROMPT_BASENAME).write_text(
            primary_prompt.strip() + "\n", encoding="utf-8"
        )
        save_thumbnail_plan(out / THUMBNAIL_PLAN_BASENAME, plan)

    def _emit(self, message: str, stage: str) -> None:
        if self._on_progress is not None:
            self._on_progress(message, stage)

    def _fail(
        self,
        message: str,
        started: float,
        *,
        extras_artifacts: list[str] | None = None,
    ) -> PipelineResult:
        del extras_artifacts
        return PipelineResult.failed(
            message,
            errors=[message],
            execution_time_ms=int((time.perf_counter() - started) * 1000),
        )


def _normalize_hook(text: str, max_words: int = 4) -> str:
    words = [w for w in (text or "").strip().upper().split() if w]
    if not words:
        return "SECRET FOUND"
    limit = max(1, min(8, int(max_words or 4)))
    return " ".join(words[:limit])


class _Cancelled(Exception):
    pass
