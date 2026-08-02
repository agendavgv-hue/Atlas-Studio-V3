"""ThumbnailService — Thumbnail Pipeline V3 orchestrator.

Flow:
  Creative Director → Thumbnail Planner → Image Prompt Builder →
  AI Image Generator → Brand Composer → Reference Compare →
  Thumbnail Critic (≥90 or retry) → Export + thumbnail_debug.json

Select mode remains a simple middle-image copy path.
"""

from __future__ import annotations

import copy
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.providers.base import TextProvider
from app.providers.errors import ProviderError
from app.providers.image_base import ImageProvider
from app.thumbnail.analyzer import ThumbnailAnalysis, ThumbnailAnalyzer
from app.thumbnail.anti_ai import AntiAiRules, AntiAiRulesLoader
from app.thumbnail.composition import CompositionPlan, CompositionPlanner
from app.thumbnail.concept_planner import ConceptPlan, ThumbnailConceptPlanner
from app.thumbnail.critic import (
    PrimaryVariantCritic,
    ThumbnailCandidate,
    ThumbnailCritic,
    ThumbnailCriticResult,
)
from app.thumbnail.critique import PromptCritique, ThumbnailCritiquePlanner
from app.thumbnail.dna_loader import ChannelDNA, ChannelDNALoader
from app.thumbnail.exporter import ThumbnailExporter
from app.thumbnail.generator import ThumbnailGenerator
from app.thumbnail.manifest import (
    ManifestGeneration,
    ManifestOutput,
    ManifestText,
    ThumbnailManifest,
)
from app.thumbnail.memory import (
    ThumbnailMemoryRecord,
    ThumbnailMemoryStore,
    ThumbnailMemoryVariant,
)
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.naming import (
    THUMBNAIL_BASENAME,
    THUMBNAIL_CONCEPTS_BASENAME,
    THUMBNAIL_CRITIQUE_BASENAME,
    THUMBNAIL_FOLDER,
    THUMBNAIL_HISTORY_BASENAME,
    THUMBNAIL_MEMORY_BASENAME,
    THUMBNAIL_PROMPT_BASENAME,
    THUMBNAIL_PROMPT_QUALITY_BASENAME,
    THUMBNAIL_QUALITY_BASENAME,
    THUMBNAIL_STRATEGY_BASENAME,
    THUMBNAIL_TITLE_BASENAME,
    VARIANT_BASENAMES,
    thumbnail_concepts_path,
    thumbnail_history_path,
    thumbnail_manifest_path,
    thumbnail_memory_path,
    thumbnail_prompt_quality_path,
    thumbnail_quality_path,
)
from app.models.thumbnail_dna import ThumbnailDNA
from app.services.thumbnail_dna_service import ThumbnailDNAService
from app.thumbnail.prompt_builder import ThumbnailPromptBuilder, ThumbnailPromptPlan
from app.thumbnail.intelligence.context import load_intelligence_context
from app.thumbnail.intelligence.planner import ThumbnailPlanner
from app.thumbnail.intelligence.prompt_builder import ThumbnailIntelligencePromptBuilder
from app.thumbnail.intelligence.consistency import score_thumbnail_consistency
from app.thumbnail.prompt_intelligence import ModelProfileLoader, write_prompt_quality_report
from app.thumbnail.quality import (
    QualityEvaluationContext,
    QualityEvaluator,
    QualityGate,
    QualityGateResult,
    QualityHistoryEntry,
    RuleBasedQualityEvaluator,
    ThumbnailQualityHistory,
    write_quality_report,
)
from app.thumbnail.settings import ThumbnailSettings
from app.thumbnail.style_loader import ChannelStyleLoader, ChannelThumbnailStyle
from app.thumbnail.thumbnail_director import ThumbnailDirector, ThumbnailStrategy

ProgressCallback = Callable[[str, str], None]


class _ThumbnailCancelled(Exception):
    """Internal signal when the user cancels mid-generation."""


@dataclass
class _GenerationBatch:
    variants: list[tuple[str, bytes]]
    snapshots: list[dict]
    candidates: list[ThumbnailCandidate]
    critic_result: ThumbnailCriticResult
    primary_id: str
    primary_snapshot: dict
    quality: QualityGateResult
    quality_context: QualityEvaluationContext
    attempt: int


class ThumbnailService:
    """Professional YouTube thumbnail designer for one project."""

    def __init__(
        self,
        settings: ThumbnailSettings,
        *,
        image_provider: ImageProvider | None = None,
        text_provider: TextProvider | None = None,
        style_loader: ChannelStyleLoader | None = None,
        dna_loader: ChannelDNALoader | None = None,
        anti_ai_loader: AntiAiRulesLoader | None = None,
        director: ThumbnailDirector | None = None,
        analyzer: ThumbnailAnalyzer | None = None,
        composition_planner: CompositionPlanner | None = None,
        prompt_builder: ThumbnailPromptBuilder | None = None,
        critique_planner: ThumbnailCritiquePlanner | None = None,
        critic: ThumbnailCritic | None = None,
        quality_evaluator: QualityEvaluator | None = None,
        quality_gate: QualityGate | None = None,
        model_profile_loader: ModelProfileLoader | None = None,
        generator: ThumbnailGenerator | None = None,
        exporter: ThumbnailExporter | None = None,
        memory_store: ThumbnailMemoryStore | None = None,
        dna_service: ThumbnailDNAService | None = None,
        data_root: Path | None = None,
        app_config=None,
        concept_planner: ThumbnailConceptPlanner | None = None,
        on_progress: ProgressCallback | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self._settings = settings
        self._image_provider = image_provider
        self._text_provider = text_provider
        self._style_loader = style_loader or ChannelStyleLoader()
        self._dna_loader = dna_loader or ChannelDNALoader()
        self._anti_ai_loader = anti_ai_loader or AntiAiRulesLoader()
        self._director = director
        self._analyzer = analyzer
        self._composition_planner = composition_planner or CompositionPlanner()
        self._prompt_builder = prompt_builder or ThumbnailPromptBuilder(
            profile_loader=model_profile_loader,
            model_name=str(getattr(settings, "model", "") or ""),
        )
        self._critique_planner = critique_planner
        self._critic = critic or PrimaryVariantCritic(settings.primary_variant or "A")
        evaluator = quality_evaluator or RuleBasedQualityEvaluator()
        self._quality_gate = quality_gate or QualityGate(
            evaluator,
            threshold=int(getattr(settings, "quality_threshold", 80) or 80),
        )
        self._generator = generator or ThumbnailGenerator(image_provider)
        self._exporter = exporter or ThumbnailExporter()
        self._memory_store = memory_store or ThumbnailMemoryStore()
        self._dna_service = dna_service
        self._data_root = Path(data_root) if data_root is not None else None
        self._app_config = app_config
        self._concept_planner = concept_planner
        self._on_progress = on_progress
        self._cancel_check = cancel_check
        self._last_manifest: ThumbnailManifest | None = None
        self._last_strategy: ThumbnailStrategy | None = None
        self._last_analysis: ThumbnailAnalysis | None = None
        self._last_composition: CompositionPlan | None = None
        self._last_dna: ChannelDNA | None = None
        self._last_thumbnail_dna: ThumbnailDNA | None = None
        self._last_concepts: ConceptPlan | None = None
        self._last_intelligence = None
        self._last_consistency = None
        self._last_critiques: list[PromptCritique] | None = None
        self._last_critic_result: ThumbnailCriticResult | None = None
        self._last_memory: ThumbnailMemoryRecord | None = None
        self._last_quality: QualityGateResult | None = None
        self._last_quality_history: ThumbnailQualityHistory | None = None

    @property
    def last_manifest(self) -> ThumbnailManifest | None:
        return self._last_manifest

    @property
    def last_strategy(self) -> ThumbnailStrategy | None:
        return self._last_strategy

    @property
    def last_analysis(self) -> ThumbnailAnalysis | None:
        return self._last_analysis

    @property
    def last_composition(self) -> CompositionPlan | None:
        return self._last_composition

    @property
    def last_dna(self) -> ChannelDNA | None:
        return self._last_dna

    @property
    def last_thumbnail_dna(self) -> ThumbnailDNA | None:
        return self._last_thumbnail_dna

    @property
    def last_concepts(self) -> ConceptPlan | None:
        return self._last_concepts

    @property
    def last_critiques(self) -> list[PromptCritique] | None:
        return self._last_critiques

    @property
    def last_critic_result(self) -> ThumbnailCriticResult | None:
        return self._last_critic_result

    @property
    def last_memory(self) -> ThumbnailMemoryRecord | None:
        return self._last_memory

    @property
    def last_quality(self) -> QualityGateResult | None:
        return self._last_quality

    @property
    def last_quality_history(self) -> ThumbnailQualityHistory | None:
        return self._last_quality_history

    def validate_ready(self, *, script_text: str = "", images: list[Path] | None = None) -> list[str]:
        errors: list[str] = []
        mode = self._resolved_mode()
        if mode is ThumbnailMode.SELECT:
            if not images:
                errors.append("No images found. Generate Images before selecting a thumbnail.")
            return errors

        if not (script_text or "").strip():
            errors.append("No script found. Generate Production before creating a thumbnail.")
        if self._text_provider is None:
            errors.append("No text provider is configured for thumbnail analysis.")
        if self._image_provider is None:
            errors.append("No image provider is configured for thumbnail generation.")
        else:
            try:
                self._image_provider.validate_ready()
            except ProviderError as exc:
                errors.append(str(exc))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Image provider validation failed: {exc}")
        return errors

    def create_thumbnail(
        self,
        context: PipelineContext,
        *,
        script_text: str,
        images: list[Path] | None = None,
        sheet_text: str = "",
    ) -> PipelineResult:
        started = time.perf_counter()
        mode = self._resolved_mode()
        self._emit("Pipeline started", "started")

        if mode is ThumbnailMode.SELECT:
            return self._create_select_thumbnail(
                context, images=images or [], started=started
            )

        return self._create_intelligent_thumbnail(
            context,
            script_text=script_text,
            sheet_text=sheet_text,
            started=started,
        )

    def _create_intelligent_thumbnail(
        self,
        context: PipelineContext,
        *,
        script_text: str,
        sheet_text: str = "",
        started: float,
    ) -> PipelineResult:
        if self._should_cancel():
            return PipelineResult.cancelled()

        # Thumbnail Pipeline V3 — definitive path when Channel Studio data root exists.
        if self._data_root is not None:
            from app.thumbnail.pipeline import ThumbnailPipelineEngine
            from app.thumbnail.pipeline.critic import DEFAULT_CRITIC_THRESHOLD

            engine = ThumbnailPipelineEngine(
                self._settings,
                image_provider=self._image_provider,
                text_provider=self._text_provider,
                data_root=self._data_root,
                on_progress=self._on_progress,
                should_cancel=self._should_cancel,
                critic_threshold=max(
                    DEFAULT_CRITIC_THRESHOLD,
                    int(getattr(self._settings, "quality_threshold", 0) or 0),
                )
                if int(getattr(self._settings, "quality_threshold", 0) or 0) >= 90
                else DEFAULT_CRITIC_THRESHOLD,
                app_config=self._app_config,
            )
            result = engine.run(
                context, script_text=script_text, sheet_text=sheet_text
            )
            # Preserve started clock for UI consistency when engine reports 0.
            if result.execution_time_ms <= 0:
                result.execution_time_ms = self._elapsed_ms(started)
            return result

        return self._create_intelligent_thumbnail_legacy(
            context,
            script_text=script_text,
            sheet_text=sheet_text,
            started=started,
        )

    def _create_intelligent_thumbnail_legacy(
        self,
        context: PipelineContext,
        *,
        script_text: str,
        sheet_text: str = "",
        started: float,
    ) -> PipelineResult:
        if self._should_cancel():
            return PipelineResult.cancelled()

        # Creative Director Engine — always before prompt construction.
        director_master = ""
        thumb_profile = None
        image_profile = None
        brief = context.creative_brief
        if brief is None and self._data_root is not None:
            try:
                from app.creative.engine import CreativeDirectorEngine

                engine = CreativeDirectorEngine(self._data_root)
                brief = engine.build_brief(
                    context.channel_name,
                    project=context.project,
                    script_text=script_text,
                    sheet_text=sheet_text,
                )
                object.__setattr__(context, "creative_brief", brief)
            except Exception:  # noqa: BLE001
                brief = None
        if brief is not None and self._data_root is not None:
            try:
                from app.creative.engine import CreativeDirectorEngine
                from app.creative.engine.style_profile_service import StyleProfileService

                engine = CreativeDirectorEngine(self._data_root)
                engine.enrich_project(
                    brief, script_text=script_text, sheet_text=sheet_text
                )
                profiles = StyleProfileService(self._data_root)
                thumb_profile = profiles.ensure_thumbnail_profile(context.channel_name)
                image_profile = profiles.ensure_image_profile(context.channel_name)
                director_master = engine.create_thumbnail_prompt(
                    brief, subject=context.project.idea or context.project.name
                )
                if thumb_profile is not None:
                    director_master = (
                        director_master + "\n\n" + thumb_profile.prompt_block()
                    )
                engine.write_report(
                    context.project_dir,
                    brief,
                    domain="thumbnail",
                    master_prompt_text=director_master,
                    thumbnail_profile_loaded=True,
                    image_profile_loaded=image_profile is not None,
                    notes=[
                        "Thumbnail generator used Creative Director as PRIMARY prompt.",
                        f"Thumbnail refs: {thumb_profile.reference_count if thumb_profile else 0}",
                        f"Image refs: {image_profile.reference_count if image_profile else 0}",
                    ],
                )
                self._emit(
                    f"Creative Director · {brief.reference_count} refs · "
                    f"{len(brief.enabled_rules)} rules · "
                    f"style profile "
                    f"{thumb_profile.reference_count if thumb_profile else 0} thumbs · "
                    f"prompt {len(director_master)} chars",
                    "creative_director",
                )
            except Exception:  # noqa: BLE001
                director_master = ""
                thumb_profile = None
                image_profile = None

        # Channel DNA + Thumbnail Intelligence (Director / Brand / Style / DNA).
        style = self._style_loader.get_style(context.channel_name)
        dna = self._dna_loader.get_dna(context.channel_name)
        anti_ai = self._anti_ai_loader.load()
        self._last_dna = dna
        thumb_dna = self._load_thumbnail_dna(context)
        self._last_thumbnail_dna = thumb_dna
        intelligence = None
        if self._data_root is not None:
            try:
                intelligence = load_intelligence_context(
                    self._data_root,
                    context.channel_name,
                    text_provider=self._text_provider,
                )
                self._last_intelligence = intelligence
                if intelligence.dna is not None:
                    thumb_dna = intelligence.dna
                    self._last_thumbnail_dna = thumb_dna
            except Exception:  # noqa: BLE001
                intelligence = None

        self._emit(f"Channel DNA: {dna.display_name}", "dna")
        if intelligence is not None:
            self._emit(
                f"Thumbnail Intelligence · style {intelligence.studio.style_strength:g} · "
                f"brand {intelligence.studio.brand_strength:g} · "
                f"{intelligence.reference_count} refs",
                "thumb_dna",
            )
        elif thumb_dna is not None:
            self._emit(
                f"Thumbnail DNA loaded ({thumb_dna.reference_count} refs)",
                "thumb_dna",
            )
        else:
            self._emit("No Thumbnail DNA yet — using channel style defaults", "thumb_dna")

        if self._should_cancel():
            return PipelineResult.cancelled()

        # Think → choose via ThumbnailPlanner (Creative Director aware).
        self._emit("Planning thumbnail concepts", "concepts")
        concept_plan: ConceptPlan | None = None
        try:
            if intelligence is not None and self._text_provider is not None:
                thumb_plan = ThumbnailPlanner(self._text_provider).plan(
                    script_text=script_text,
                    sheet_text=sheet_text,
                    channel_name=context.channel_name,
                    channel_dna_text=dna.dna_block()
                    if hasattr(dna, "dna_block")
                    else dna.signature,
                    intelligence=intelligence,
                )
                concept_plan = thumb_plan.concept_plan
            else:
                concept_plan = self._get_concept_planner().plan(
                    script_text=script_text,
                    channel_name=context.channel_name,
                    sheet_text=sheet_text,
                    channel_dna_text=dna.dna_block()
                    if hasattr(dna, "dna_block")
                    else dna.signature,
                    thumbnail_dna=thumb_dna,
                )
            strategy = concept_plan.strategy
            concept_plan.write_json(thumbnail_concepts_path(context.project_dir))
            self._last_concepts = concept_plan
            self._emit(
                f"Chose concept: {concept_plan.chosen.title}",
                "concept_chosen",
            )
        except (ProviderError, ValueError, OSError, TypeError, KeyError):
            # Backward-compatible fallback to legacy director.
            self._emit("Concept planner unavailable — using director", "concepts")
            try:
                strategy = self._get_director().direct(
                    script_text, channel_name=context.channel_name
                )
            except ProviderError as exc:
                return self._fail(str(exc), started)

        self._last_strategy = strategy
        self._emit(
            f"Emotion: {strategy.emotion} — {strategy.click_reason}",
            "strategy",
        )

        if self._should_cancel():
            return PipelineResult.cancelled()

        self._emit("Analyzing hero subject + hook", "analyze")
        try:
            analysis = self._get_analyzer().analyze(
                script_text,
                strategy=strategy,
                channel_name=context.channel_name,
            )
        except ProviderError as exc:
            return self._fail(str(exc), started)

        # Prefer concept hero when concept planner ran successfully.
        if concept_plan is not None and strategy.hero_subject:
            analysis = ThumbnailAnalysis(
                hero_subject=strategy.hero_subject or analysis.hero_subject,
                hook=analysis.hook,
                rationale=concept_plan.chosen_reason or analysis.rationale,
            )

        self._last_analysis = analysis
        self._emit(f"Hero subject: {analysis.hero_subject}", "hero")

        if self._should_cancel():
            return PipelineResult.cancelled()

        self._emit(f"Hook: {analysis.hook}", "hook")
        self._emit(f"Channel style: {style.display_name}", "style")

        composition = self._composition_planner.plan(
            strategy=strategy,
            style=style,
            thumbnail_dna=thumb_dna,
        )
        self._last_composition = composition
        self._emit("Composition planned", "composition")

        plans = self._prompt_builder.build_variants(
            strategy=strategy,
            hero_subject=analysis.hero_subject,
            composition=composition,
            style=style,
            dna=dna,
            anti_ai=anti_ai,
            model_name=str(getattr(self._settings, "model", "") or ""),
        )
        # Creative Director PRIMARY prompt — Channel Studio identity leads.
        if brief is not None and director_master:
            try:
                from app.thumbnail.director_prompt import build_director_led_thumbnail_plans

                plans = build_director_led_thumbnail_plans(
                    brief,
                    hero_subject=analysis.hero_subject,
                    hook=analysis.hook,
                    emotion=strategy.emotion,
                    thumbnail_profile=thumb_profile,
                    image_profile=image_profile,
                )
                self._emit("Director-led thumbnail prompts active", "prompts")
            except Exception:  # noqa: BLE001
                # Fall back to appending director_master onto Prompt Intelligence plans.
                plans = [
                    ThumbnailPromptPlan(
                        variant_id=p.variant_id,
                        variant_key=p.variant_key,
                        variant_label=p.variant_label,
                        prompt=f"{director_master}\n\nSCENE DELTA: {p.prompt}",
                        negative_prompt=p.negative_prompt,
                        blocks=p.blocks,
                        prompt_quality=p.prompt_quality,
                        model_profile=p.model_profile,
                    )
                    for p in plans
                ]
        else:
            intel_block = director_master
            if not intel_block and intelligence is not None and concept_plan is not None:
                try:
                    from app.thumbnail.intelligence.planner import ThumbnailPlan as _TP

                    built_intel = ThumbnailIntelligencePromptBuilder().build(
                        plan=_TP(
                            concept_plan=concept_plan,
                            intelligence_brief=intelligence.identity_brief(),
                            selected_scene=concept_plan.selected_scene,
                            chosen_title=concept_plan.chosen.title,
                        ),
                        intelligence=intelligence,
                        hero_subject=analysis.hero_subject,
                        hook=analysis.hook,
                    )
                    intel_block = built_intel.style_block
                    consistency = score_thumbnail_consistency(
                        intelligence,
                        prompt=built_intel.prompt,
                        hook=analysis.hook,
                    )
                    self._last_consistency = consistency
                    self._emit(
                        f"Consistency {consistency.overall:.0f}% "
                        f"(brand {consistency.brand:.0f} · style {consistency.style:.0f} · "
                        f"layout {consistency.layout:.0f} · identity {consistency.identity:.0f})",
                        "consistency",
                    )
                except Exception:  # noqa: BLE001
                    intel_block = intelligence.identity_brief()
            elif not intel_block and intelligence is not None:
                intel_block = intelligence.identity_brief()
            elif not intel_block and thumb_dna is not None:
                intel_block = thumb_dna.prompt_block()

            if intel_block:
                plans = [
                    ThumbnailPromptPlan(
                        variant_id=p.variant_id,
                        variant_key=p.variant_key,
                        variant_label=p.variant_label,
                        prompt=f"{p.prompt}, {intel_block}",
                        negative_prompt=p.negative_prompt,
                        blocks=p.blocks,
                        prompt_quality=p.prompt_quality,
                        model_profile=p.model_profile,
                    )
                    for p in plans
                ]
        self._emit("Thumbnail prompts ready", "prompts")

        prompt_quality_path = thumbnail_prompt_quality_path(context.project_dir)
        try:
            primary_built = self._prompt_builder.last_primary
            if primary_built is not None:
                write_prompt_quality_report(
                    prompt_quality_path,
                    primary_built.quality,
                    blocks=primary_built.blocks,
                )
                self._emit(
                    f"Prompt score {primary_built.quality.total}/100 "
                    f"({primary_built.profile.display_name})",
                    "prompt_quality",
                )
        except OSError as exc:
            return self._fail(f"Failed to write prompt quality report: {exc}", started)

        if self._should_cancel():
            return PipelineResult.cancelled()

        self._emit("Critiquing prompts against Channel DNA", "critique")
        try:
            plans, critiques = self._get_critique_planner().critique_plans(
                plans,
                strategy=strategy,
                hero_subject=analysis.hero_subject,
                dna=dna,
                anti_ai=anti_ai,
                channel_name=context.channel_name,
            )
        except ProviderError as exc:
            return self._fail(str(exc), started)

        self._last_critiques = critiques
        rewritten = sum(1 for item in critiques if item.rewritten)
        self._emit(
            f"Critique done · {rewritten} prompt(s) rewritten",
            "critique_done",
        )

        primary_prompt = self._prompt_builder.primary_prompt_text(plans)
        loras = self._settings.resolved_loras()
        max_attempts = max(1, int(getattr(self._settings, "max_quality_attempts", 3) or 3))
        history = ThumbnailQualityHistory.read_json(
            thumbnail_history_path(context.project_dir)
        )
        approved_batch: _GenerationBatch | None = None

        for attempt in range(1, max_attempts + 1):
            if self._should_cancel():
                return PipelineResult.cancelled()

            self._emit(
                f"Quality attempt {attempt}/{max_attempts}",
                f"qa_attempt_{attempt}",
            )
            try:
                batch = self._generate_and_score_batch(
                    plans=plans,
                    critiques=critiques,
                    strategy=strategy,
                    analysis=analysis,
                    dna=dna,
                    composition=composition,
                    channel_name=context.channel_name,
                    loras=loras,
                    attempt=attempt,
                )
            except _ThumbnailCancelled:
                return PipelineResult.cancelled()
            except ProviderError as exc:
                return self._fail(str(exc), started)
            except ValueError as exc:
                return self._fail(str(exc), started)

            history.append(
                QualityHistoryEntry(
                    attempt=attempt,
                    score=batch.quality.total,
                    approved=batch.quality.approved,
                    date="",
                    channel=context.channel_name,
                    hero_subject=analysis.hero_subject,
                    hook=analysis.hook,
                    prompt=str(batch.primary_snapshot.get("prompt") or primary_prompt),
                    seed=int(
                        batch.primary_snapshot.get("seed")
                        if batch.primary_snapshot.get("seed") is not None
                        else -1
                    ),
                    model=str(batch.primary_snapshot.get("model") or ""),
                    rejection_reason=""
                    if batch.quality.approved
                    else batch.quality.rejection_reason,
                    variant_id=batch.primary_id,
                    quality=batch.quality.to_report(),
                    extras={"attempt": attempt, "max_attempts": max_attempts},
                )
            )

            if batch.quality.approved:
                approved_batch = batch
                self._emit(
                    f"QA approved · score {batch.quality.total}/{self._quality_gate.threshold}",
                    "qa_approved",
                )
                break

            self._emit(
                f"QA rejected · score {batch.quality.total} < {self._quality_gate.threshold}",
                "qa_rejected",
            )
            if attempt < max_attempts:
                self._emit("Regenerating after QA reject", "qa_retry")

        history_path = thumbnail_history_path(context.project_dir)
        try:
            history.write_json(history_path)
            self._last_quality_history = history
        except OSError as exc:
            return self._fail(f"Failed to write thumbnail history: {exc}", started)

        if approved_batch is None:
            best = max(history.entries, key=lambda item: item.score, default=None)
            best_score = best.score if best else 0
            if best is not None and best.quality:
                try:
                    quality_path = thumbnail_quality_path(context.project_dir)
                    quality_path.parent.mkdir(parents=True, exist_ok=True)
                    report = dict(best.quality)
                    report["approved"] = False
                    report["rejection_reason"] = (
                        f"Best score {best_score} after {max_attempts} attempts "
                        f"(threshold {self._quality_gate.threshold})"
                    )
                    quality_path.write_text(
                        json.dumps(report, indent=2) + "\n", encoding="utf-8"
                    )
                except OSError:
                    pass
            return self._fail(
                f"Thumbnail QA failed after {max_attempts} attempts "
                f"(best score {best_score}, need ≥ {self._quality_gate.threshold}).",
                started,
            )

        batch = approved_batch
        self._last_critic_result = batch.critic_result
        self._last_quality = batch.quality

        self._emit("Exporting thumbnail package", "export")
        try:
            logo_path = None
            frame_path = None
            logo_placement = None
            fill_hex = ""
            outline_hex = ""
            font_family = ""
            max_words = 4
            align_left: bool | None = True
            if brief is not None and self._data_root is not None:
                from app.channels.studio.service import ChannelStudioService
                from app.thumbnail.intelligence.branding import ThumbnailBrandingService
                from app.thumbnail.intelligence.settings import ThumbnailStudioSettings

                studio = ChannelStudioService(self._data_root)
                logo_rel = brief.brand.thumbnail_logo or brief.brand.logo
                logo_path = studio.resolve_asset(context.channel_name, logo_rel)
                frame_rel = (
                    brief.brand.thumbnail_frame
                    or str((brief.brand.extras or {}).get("thumbnail_frame") or "")
                ).strip()
                frame_path = (
                    studio.resolve_asset(context.channel_name, frame_rel)
                    if frame_rel
                    else None
                )
                settings = ThumbnailStudioSettings(
                    max_words=int(brief.thumbnail.max_words or 4),
                    logo_visible=bool(brief.thumbnail.logo_visible),
                    logo_position=(
                        (thumb_profile.logo_bias if thumb_profile and brief.thumbnail.logo_position == "auto" else None)
                        or str(brief.thumbnail.logo_position or "auto")
                    ),
                    logo_size=float(brief.thumbnail.logo_size or 0.12),
                    contrast=str(brief.thumbnail.contrast or "very_high"),
                    negative_space=str(brief.thumbnail.negative_space or "left"),
                    creativity=float(brief.thumbnail.creativity or 60),
                    style_strength=float(brief.thumbnail.style_strength or 80),
                    brand_strength=float(brief.thumbnail.brand_strength or 85),
                )
                logo_placement = ThumbnailBrandingService().resolve_logo_placement(
                    settings=settings,
                    dna=thumb_dna,
                    subject_position=(
                        thumb_profile.subject_bias if thumb_profile else ""
                    ),
                )
                fill_hex = brief.brand.primary_color or ""
                outline_hex = brief.brand.secondary_color or "#1A1208"
                if brief.brand.fonts:
                    font_family = brief.brand.fonts[0]
                max_words = int(brief.thumbnail.max_words or 4)
                if thumb_profile is not None:
                    align_left = thumb_profile.text_position != "right"

            exported = self._exporter.export_package(
                context.project_dir,
                hook=analysis.hook,
                variants=batch.variants,
                primary_variant_id=batch.primary_id,
                strategy=strategy,
                primary_prompt=primary_prompt,
                critique_reports=[item.to_dict() for item in critiques],
                channel_name=context.channel_name,
                logo_path=logo_path,
                frame_path=frame_path,
                logo_placement=logo_placement,
                text_fill_hex=fill_hex,
                text_outline_hex=outline_hex,
                font_family=font_family,
                max_words=max_words,
                text_align_left=align_left,
            )
        except (ValueError, OSError) as exc:
            return self._fail(f"Thumbnail export failed: {exc}", started)

        if not exported.primary_path.is_file():
            return self._fail(
                "Thumbnail export did not create thumbnail.png.",
                started,
                errors=["thumbnail.png is missing"],
            )

        quality_path = thumbnail_quality_path(context.project_dir)
        try:
            write_quality_report(
                quality_path, batch.quality.score, approved=True
            )
        except OSError as exc:
            return self._fail(f"Failed to write thumbnail quality report: {exc}", started)

        first = batch.primary_snapshot
        memory = ThumbnailMemoryRecord(
            channel_name=context.channel_name,
            project_name=getattr(context, "project_name", "") or "",
            hero_subject=analysis.hero_subject,
            emotion=strategy.emotion,
            click_reason=strategy.click_reason,
            hook=analysis.hook,
            composition=composition.to_dict(),
            channel_dna=dna.to_dict(),
            primary_prompt=str(first.get("prompt") or primary_prompt),
            negative_prompt=str(first.get("negative_prompt") or ""),
            seed=int(first.get("seed") if first.get("seed") is not None else -1),
            model=str(first.get("model") or ""),
            loras=list(loras),
            primary_variant_id=batch.primary_id,
            selection_method=batch.critic_result.selection_method,
            critic_ready=True,
            critic_result=batch.critic_result.to_dict(),
            variants=[
                ThumbnailMemoryVariant(
                    variant_id=str(item["variant_id"]),
                    variant_key=str(item.get("variant_key") or ""),
                    prompt=str(item.get("prompt") or ""),
                    negative_prompt=str(item.get("negative_prompt") or ""),
                    seed=int(item.get("seed") if item.get("seed") is not None else -1),
                    model=str(item.get("model") or ""),
                    loras=list(item.get("loras") or []),
                    provider_id=str(item.get("provider_id") or ""),
                    width=int(item.get("width") or 0),
                    height=int(item.get("height") or 0),
                    file_name=str(item.get("file_name") or ""),
                    critique=dict(item.get("critique") or {}),
                )
                for item in batch.snapshots
            ],
            extras={
                "anti_ai_forbidden": list(anti_ai.forbidden),
                "dominant_feeling": strategy.dominant_feeling,
                "quality": batch.quality.to_report(),
                "qa_attempt": batch.attempt,
            },
        )
        memory_path = thumbnail_memory_path(context.project_dir)
        try:
            self._memory_store.save(memory_path, memory)
            self._last_memory = memory
        except OSError as exc:
            return self._fail(f"Failed to write thumbnail memory: {exc}", started)

        self._emit("Thumbnail memory saved", "memory")

        manifest = self._build_manifest(
            analysis=analysis,
            strategy=strategy,
            style=style,
            dna=dna,
            composition=composition,
            critiques=critiques,
            batch=batch,
            primary_prompt=primary_prompt,
            loras=loras,
        )
        manifest_path = thumbnail_manifest_path(context.project_dir)
        try:
            manifest.write_json(manifest_path)
            self._last_manifest = manifest
        except OSError as exc:
            return self._fail(f"Failed to write thumbnail manifest: {exc}", started)

        self._emit("Manifest written", "manifest")
        self._emit("Pipeline finished", "finished")

        artifacts = [
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_STRATEGY_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_CONCEPTS_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_PROMPT_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_PROMPT_QUALITY_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_TITLE_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_CRITIQUE_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_QUALITY_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_HISTORY_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_MEMORY_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{THUMBNAIL_BASENAME}",
            f"{THUMBNAIL_FOLDER}/{manifest_path.name}",
        ]
        for vid, _ in batch.variants:
            name = VARIANT_BASENAMES.get(vid)
            if name:
                artifacts.append(f"{THUMBNAIL_FOLDER}/{name}")

        return PipelineResult.success(
            f"QA approved ({batch.quality.total}/100) · {dna.display_name} · "
            f"{strategy.emotion} · hook “{analysis.hook}” · hero “{analysis.hero_subject}”",
            artifacts=artifacts,
            execution_time_ms=self._elapsed_ms(started),
        )

    def _generate_and_score_batch(
        self,
        *,
        plans: list[ThumbnailPromptPlan],
        critiques: list[PromptCritique],
        strategy: ThumbnailStrategy,
        analysis: ThumbnailAnalysis,
        dna: ChannelDNA,
        composition: CompositionPlan,
        channel_name: str,
        loras: list[str],
        attempt: int,
    ) -> _GenerationBatch:
        attempt_settings = copy.copy(self._settings)
        base_seed = int(getattr(self._settings, "seed", -1) if getattr(self._settings, "seed", -1) is not None else -1)
        if base_seed < 0:
            attempt_settings.seed = 1000 + attempt
        else:
            attempt_settings.seed = base_seed + (attempt - 1)

        variants: list[tuple[str, bytes]] = []
        snapshots: list[dict] = []
        candidates: list[ThumbnailCandidate] = []
        critique_by_id = {item.variant_id.upper(): item for item in critiques}
        qa_contexts: list[QualityEvaluationContext] = []

        for plan in plans:
            if self._should_cancel():
                raise _ThumbnailCancelled()
            self._emit(
                f"Generating variant {plan.variant_id} ({plan.variant_label})",
                f"variant_{plan.variant_id.lower()}",
            )
            generated = self._generator.generate_variant(plan, settings=attempt_settings)
            variants.append((plan.variant_id, generated.image_png))
            file_name = VARIANT_BASENAMES.get(
                plan.variant_id, f"thumbnail_{plan.variant_id}.png"
            )
            critique = critique_by_id.get(plan.variant_id.upper())
            critique_dict = critique.to_dict() if critique else {}
            snapshot = {
                "variant_id": plan.variant_id,
                "variant_key": plan.variant_key,
                "prompt": plan.prompt,
                "negative_prompt": plan.negative_prompt,
                "provider_id": generated.provider_id,
                "seed": generated.seed,
                "model": generated.model,
                "loras": list(loras),
                "width": generated.width,
                "height": generated.height,
                "file_name": file_name,
                "critique": critique_dict,
                "qa_attempt": attempt,
            }
            snapshots.append(snapshot)
            candidates.append(
                ThumbnailCandidate(
                    variant_id=plan.variant_id,
                    variant_key=plan.variant_key,
                    image_png=generated.image_png,
                    prompt=plan.prompt,
                    file_name=file_name,
                    seed=generated.seed,
                    model=generated.model,
                )
            )
            qa_contexts.append(
                QualityEvaluationContext(
                    image_png=generated.image_png,
                    prompt=plan.prompt,
                    negative_prompt=plan.negative_prompt,
                    hero_subject=analysis.hero_subject,
                    hook=analysis.hook,
                    emotion=strategy.emotion,
                    click_reason=strategy.click_reason,
                    channel_name=channel_name,
                    channel_dna=dna.to_dict(),
                    composition=composition.to_dict(),
                    critique=critique_dict,
                    variant_id=plan.variant_id,
                    variant_key=plan.variant_key,
                    seed=generated.seed,
                    model=generated.model,
                    loras=tuple(loras),
                    attempt=attempt,
                )
            )

        self._emit("Selecting primary thumbnail", "critic")
        critic_result = self._critic.select(candidates)
        primary_id = critic_result.winner_variant_id

        self._emit("Running quality assurance", "qa")
        # Prefer an approved variant; fall back to critic winner for scoring/history.
        picked = self._quality_gate.pick_best_approved(qa_contexts)
        if picked is not None:
            quality, quality_context = picked
            primary_id = quality_context.variant_id or primary_id
        else:
            by_id = {ctx.variant_id.upper(): ctx for ctx in qa_contexts}
            quality_context = by_id.get(primary_id.upper()) or qa_contexts[0]
            quality = self._quality_gate.assess(quality_context)

        primary_snapshot = next(
            (
                item
                for item in snapshots
                if str(item["variant_id"]).upper() == primary_id.upper()
            ),
            snapshots[0] if snapshots else {},
        )
        return _GenerationBatch(
            variants=variants,
            snapshots=snapshots,
            candidates=candidates,
            critic_result=critic_result,
            primary_id=primary_id,
            primary_snapshot=primary_snapshot,
            quality=quality,
            quality_context=quality_context,
            attempt=attempt,
        )

    def _build_manifest(
        self,
        *,
        analysis: ThumbnailAnalysis,
        strategy: ThumbnailStrategy,
        style: ChannelThumbnailStyle,
        dna: ChannelDNA,
        composition: CompositionPlan,
        critiques: list[PromptCritique],
        batch: _GenerationBatch,
        primary_prompt: str,
        loras: list[str],
    ) -> ThumbnailManifest:
        first = batch.primary_snapshot
        return ThumbnailManifest(
            mode=ThumbnailMode.INTELLIGENT.value,
            source_image_path=None,
            rationale=analysis.rationale or strategy.rationale,
            text=ManifestText(title="", hook=analysis.hook),
            output=ManifestOutput(
                folder=THUMBNAIL_FOLDER,
                filename=THUMBNAIL_BASENAME,
                width=self._settings.width,
                height=self._settings.height,
            ),
            generation=ManifestGeneration(
                provider_id=str(first.get("provider_id") or ""),
                prompt=str(first.get("prompt") or primary_prompt),
                negative_prompt=str(first.get("negative_prompt") or ""),
                width=int(first.get("width") or self._settings.width),
                height=int(first.get("height") or self._settings.height),
                seed=int(first.get("seed") if first.get("seed") is not None else -1),
                model=str(first.get("model") or ""),
                extras={
                    "hero_subject": analysis.hero_subject,
                    "hook": analysis.hook,
                    "emotion": strategy.emotion,
                    "click_reason": strategy.click_reason,
                    "channel_style": style.channel_key,
                    "channel_dna": dna.to_dict(),
                    "composition": composition.to_dict(),
                    "loras": list(loras),
                    "critique": [item.to_dict() for item in critiques],
                    "critic": batch.critic_result.to_dict(),
                    "quality": batch.quality.to_report(),
                    "qa_attempt": batch.attempt,
                    "variants": batch.snapshots,
                },
            ),
            exported=True,
            extras={
                "hero_subject": analysis.hero_subject,
                "hook": analysis.hook,
                "emotion": strategy.emotion,
                "click_reason": strategy.click_reason,
                "dominant_feeling": strategy.dominant_feeling,
                "composition": composition.to_dict(),
                "channel_dna": dna.channel_key,
                "strategy_file": THUMBNAIL_STRATEGY_BASENAME,
                "prompt_file": THUMBNAIL_PROMPT_BASENAME,
                "prompt_quality_file": THUMBNAIL_PROMPT_QUALITY_BASENAME,
                "title_file": THUMBNAIL_TITLE_BASENAME,
                "memory_file": THUMBNAIL_MEMORY_BASENAME,
                "critique_file": THUMBNAIL_CRITIQUE_BASENAME,
                "quality_file": THUMBNAIL_QUALITY_BASENAME,
                "history_file": THUMBNAIL_HISTORY_BASENAME,
                "primary_variant_id": batch.primary_id,
                "selection_method": batch.critic_result.selection_method,
                "critic_ready": True,
                "quality_approved": True,
                "quality_score": batch.quality.total,
                "variant_files": [
                    VARIANT_BASENAMES.get(vid, f"thumbnail_{vid}.png")
                    for vid, _ in batch.variants
                ],
            },
        )

    def _create_select_thumbnail(
        self,
        context: PipelineContext,
        *,
        images: list[Path],
        started: float,
    ) -> PipelineResult:
        """Legacy fallback: copy the middle project image."""
        if not images:
            return self._fail(
                "No images found. Generate Images before selecting a thumbnail.",
                started,
                errors=["No images"],
            )
        source = images[len(images) // 2]
        self._emit("Selecting project image", "selected")
        try:
            generated = self._generator.load_image_bytes(source)
            self._exporter.export_png(context.project_dir, generated.image_png)
        except (ProviderError, ValueError, OSError) as exc:
            return self._fail(str(exc), started)

        self._emit("Thumbnail exported", "exported")
        manifest = ThumbnailManifest(
            mode=ThumbnailMode.SELECT.value,
            source_image_path=str(source),
            rationale="Legacy select mode — middle project image.",
            output=ManifestOutput(
                folder=THUMBNAIL_FOLDER,
                filename=THUMBNAIL_BASENAME,
                width=self._settings.width,
                height=self._settings.height,
            ),
            exported=True,
        )
        manifest_path = thumbnail_manifest_path(context.project_dir)
        try:
            manifest.write_json(manifest_path)
            self._last_manifest = manifest
        except OSError as exc:
            return self._fail(f"Failed to write thumbnail manifest: {exc}", started)

        self._emit("Pipeline finished", "finished")
        return PipelineResult.success(
            f"Exported {THUMBNAIL_BASENAME} (select)",
            artifacts=[
                f"{THUMBNAIL_FOLDER}/{THUMBNAIL_BASENAME}",
                f"{THUMBNAIL_FOLDER}/{manifest_path.name}",
            ],
            execution_time_ms=self._elapsed_ms(started),
        )

    def _fail(
        self,
        message: str,
        started: float,
        *,
        errors: list[str] | None = None,
    ) -> PipelineResult:
        return PipelineResult.failed(
            message,
            errors=errors or [message],
            execution_time_ms=self._elapsed_ms(started),
        )

    def _resolved_mode(self) -> ThumbnailMode:
        raw = (self._settings.mode or ThumbnailMode.INTELLIGENT.value).strip().casefold()
        if raw in {ThumbnailMode.SELECT.value, "select"}:
            return ThumbnailMode.SELECT
        if raw in {
            ThumbnailMode.INTELLIGENT.value,
            ThumbnailMode.GENERATE.value,
            "intelligent",
            "generate",
        }:
            return ThumbnailMode.INTELLIGENT
        return ThumbnailMode.INTELLIGENT

    def _load_thumbnail_dna(self, context: PipelineContext) -> ThumbnailDNA | None:
        service = self._dna_service
        if service is None and self._data_root is not None:
            service = ThumbnailDNAService(self._data_root)
        if service is None:
            return None
        try:
            return service.get_thumbnail_dna(context.channel_name)
        except (OSError, ValueError):
            return None

    def _get_concept_planner(self) -> ThumbnailConceptPlanner:
        if self._concept_planner is not None:
            return self._concept_planner
        if self._text_provider is None:
            raise ProviderError("No text provider is configured for thumbnail concepts.")
        return ThumbnailConceptPlanner(self._text_provider)

    def _get_director(self) -> ThumbnailDirector:
        if self._director is not None:
            return self._director
        if self._text_provider is None:
            raise ProviderError("No text provider is configured for thumbnail direction.")
        return ThumbnailDirector(self._text_provider)

    def _get_analyzer(self) -> ThumbnailAnalyzer:
        if self._analyzer is not None:
            return self._analyzer
        if self._text_provider is None:
            raise ProviderError("No text provider is configured for thumbnail analysis.")
        return ThumbnailAnalyzer(self._text_provider)

    def _get_critique_planner(self) -> ThumbnailCritiquePlanner:
        if self._critique_planner is not None:
            return self._critique_planner
        if self._text_provider is None:
            raise ProviderError("No text provider is configured for thumbnail critique.")
        return ThumbnailCritiquePlanner(self._text_provider)

    def _should_cancel(self) -> bool:
        return self._cancel_check is not None and self._cancel_check()

    def _emit(self, message: str, stage: str) -> None:
        if self._on_progress is not None:
            self._on_progress(message, stage)

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)
