"""CreativeDirector — LLM reasoning brain (Orchestrator-selected provider)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.orchestrator import AIOrchestratorService, try_text_with_fallback
from app.ai.roles import AIRole
from app.creative.director.analysis import CreativeDirectorAnalysis
from app.creative.engine.brief import CreativeBrief
from app.creative.engine.style_profile import StyleProfile
from app.providers.errors import ProviderConfigurationError, ProviderError
from app.thumbnail.concepts.models import ConceptBoard, ThumbnailConceptIdea
from app.thumbnail.concepts.planner import ThumbnailConceptPlanner
from app.thumbnail.concepts.store import write_concept_board
from app.thumbnail.text_utils import parse_json_object

_SYSTEM = (
    "You are the Creative Director of Atlas Studio. "
    "You think carefully before any image is generated. "
    "You never write Stable Diffusion prompts. "
    "You never place text, logos, or frames in the image. "
    "You maximize curiosity and CTR for a premium documentary channel identity "
    "defined by the Channel Studio brief — never invent a generic stock look."
)

_ANALYSIS_USER = """Channel: {channel}

Creative Brief summary:
{brief}

Reference style:
{references}

Project / topic: {topic}

Script:
---
{script}
---

Production sheet (optional):
---
{sheet}
---

Analyze first. Do NOT write an image prompt.

Return ONLY JSON:
{{
  "greatest_mystery": "...",
  "most_exciting_scene": "...",
  "highest_ctr_image": "one sentence visual that would get the most clicks",
  "emotion": "curiosity|mystery|wonder|fear|adventure|epic",
  "must_show_objects": ["..."],
  "must_hide_objects": ["text", "logo", "watermark", "..."],
  "negative_space": "left|right",
  "title_placement": "left third|right third",
  "logo_placement": "bottom_left|bottom_right|top_left|top_right",
  "dominant_colors": ["#112233"],
  "composition": "rule_of_thirds|centered_hero|wide_establishing",
  "camera_angle": "eye_level|low_angle|high_angle",
  "lighting": "...",
  "rationale": "short why this wins"
}}
"""


@dataclass
class CreativeDirectorReport:
    channel_name: str
    analysis: CreativeDirectorAnalysis
    concepts: ConceptBoard | None = None
    provider_id: str = ""
    model: str = ""
    used_fallback: bool = False
    notes: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "analysis": self.analysis.to_dict(),
            "concepts": self.concepts.to_dict() if self.concepts else {},
            "provider_id": self.provider_id,
            "model": self.model,
            "used_fallback": self.used_fallback,
            "notes": list(self.notes),
            "extras": dict(self.extras),
        }


class CreativeDirector:
    """Think → analyze → invent concepts → choose best (no image generation)."""

    def __init__(self, orchestrator: AIOrchestratorService) -> None:
        self._orchestrator = orchestrator

    def direct_thumbnail(
        self,
        brief: CreativeBrief,
        *,
        script_text: str = "",
        sheet_text: str = "",
        topic: str = "",
        thumbnail_profile: StyleProfile | None = None,
        project_dir: Path | None = None,
    ) -> CreativeDirectorReport:
        analysis, resolved = self._analyze(
            brief,
            script_text=script_text,
            sheet_text=sheet_text,
            topic=topic,
            thumbnail_profile=thumbnail_profile,
        )

        # Prefer Orchestrator text for concept invent when available.
        text = resolved.provider
        from app.providers.base import TextProvider

        planner = ThumbnailConceptPlanner(
            text if isinstance(text, TextProvider) else None
        )
        # Enrich invent context via analysis notes on brief extras.
        brief.extras["creative_director_analysis"] = analysis.to_dict()
        board = planner.plan(
            brief,
            script_text=self._concept_script(script_text, topic, analysis),
            topic=topic or brief.project.topic or brief.project.idea,
            thumbnail_profile=thumbnail_profile,
            project_dir=project_dir,
        )
        # Align winner with director analysis when helpful.
        board = self._prefer_analysis_aligned(board, analysis)

        if project_dir is not None:
            write_concept_board(project_dir, board)
            self._write_artifacts(project_dir, brief, analysis, board, resolved)

        report = CreativeDirectorReport(
            channel_name=brief.channel_name,
            analysis=analysis,
            concepts=board,
            provider_id=resolved.provider_id,
            model=resolved.model,
            used_fallback=resolved.used_fallback,
            notes=[
                f"Selected concept #{board.selected_id} “{board.chosen.title}”",
                board.selected_reason,
            ],
        )
        if project_dir is not None:
            path = Path(project_dir) / "thumbnail" / "creative_director_report.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        return report

    def _analyze(
        self,
        brief: CreativeBrief,
        *,
        script_text: str,
        sheet_text: str,
        topic: str,
        thumbnail_profile: StyleProfile | None,
    ) -> tuple[CreativeDirectorAnalysis, Any]:
        refs = "No reference profile."
        if thumbnail_profile is not None:
            refs = (
                f"count={thumbnail_profile.reference_count}; "
                f"subject={thumbnail_profile.subject_bias}; "
                f"negative_space={thumbnail_profile.negative_space}; "
                f"contrast={thumbnail_profile.contrast}; "
                f"mood={thumbnail_profile.mood}; "
                f"colors={', '.join(thumbnail_profile.dominant_colors[:4])}"
            )
        brief_summary = (
            f"type={brief.general.channel_type}; niche={brief.general.niche}; "
            f"tone={brief.general.tone_of_voice}; "
            f"colors={brief.brand.primary_color},{brief.brand.secondary_color}; "
            f"thumb_emotion={brief.thumbnail.emotion}; "
            f"image_lighting={brief.image.lighting}; "
            f"personality={','.join(k for k,v in brief.personality.traits.items() if v>=70)}"
        )
        prompt = _ANALYSIS_USER.format(
            channel=brief.channel_name,
            brief=brief_summary,
            references=refs,
            topic=topic or brief.project.idea or brief.project.topic,
            script=(script_text or topic or brief.project.idea or "")[:9000],
            sheet=(sheet_text or "")[:4000],
        )
        try:
            raw, resolved = try_text_with_fallback(
                self._orchestrator,
                AIRole.CREATIVE_DIRECTOR,
                prompt,
                system=_SYSTEM,
            )
            data = parse_json_object(raw, label="Creative Director")
            analysis = CreativeDirectorAnalysis.from_dict(data)
            analysis.provider_id = resolved.provider_id
            analysis.model = resolved.model
            analysis.used_fallback = resolved.used_fallback
            if not analysis.dominant_colors:
                analysis.dominant_colors = [
                    c
                    for c in (
                        brief.brand.primary_color,
                        brief.brand.secondary_color,
                        brief.brand.accent_color,
                    )
                    if c
                ]
            return analysis, resolved
        except (ProviderError, ProviderConfigurationError, ValueError, Exception):  # noqa: BLE001
            # Heuristic fallback analysis — still generic from Channel Studio.
            try:
                resolved = self._orchestrator.resolve_text(AIRole.CREATIVE_DIRECTOR)
            except Exception:  # noqa: BLE001
                from app.ai.orchestrator import ResolvedAI
                from app.providers.base import TextProvider

                class _Null(TextProvider):
                    @property
                    def provider_id(self) -> str:
                        return "none"

                    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
                        raise ProviderError("No text provider")

                resolved = ResolvedAI(
                    role=AIRole.CREATIVE_DIRECTOR,
                    provider_id="none",
                    model="",
                    provider=_Null(),
                    used_fallback=True,
                )
            analysis = CreativeDirectorAnalysis(
                greatest_mystery=topic or brief.project.idea or "an unanswered discovery",
                most_exciting_scene=brief.project.primary_subject or "iconic subject in atmosphere",
                highest_ctr_image="one dominant subject with clear negative space for title",
                emotion=brief.thumbnail.emotion or "curiosity",
                must_show_objects=[brief.project.primary_subject or "main subject"],
                must_hide_objects=["text", "logo", "watermark", "frame", "ui"],
                negative_space=(
                    thumbnail_profile.negative_space
                    if thumbnail_profile and thumbnail_profile.negative_space != "auto"
                    else brief.thumbnail.negative_space
                    if brief.thumbnail.negative_space != "auto"
                    else "left"
                ),
                title_placement="left third",
                logo_placement=brief.thumbnail.logo_position
                if brief.thumbnail.logo_position != "auto"
                else "bottom_left",
                dominant_colors=[
                    c
                    for c in (
                        brief.brand.primary_color,
                        brief.brand.secondary_color,
                        brief.brand.accent_color,
                    )
                    if c
                ],
                composition="rule_of_thirds",
                camera_angle=brief.image.camera_style or "eye_level",
                lighting=brief.image.lighting or "cinematic rim light",
                rationale="Fallback analysis from Channel Studio (LLM unavailable).",
                provider_id=resolved.provider_id,
                model=resolved.model,
                used_fallback=True,
            )
            return analysis, resolved

    @staticmethod
    def _concept_script(script_text: str, topic: str, analysis: CreativeDirectorAnalysis) -> str:
        parts = [
            script_text.strip() or topic,
            "",
            "CREATIVE DIRECTOR CONSTRAINTS:",
            analysis.prompt_block(),
        ]
        return "\n".join(parts)

    @staticmethod
    def _prefer_analysis_aligned(
        board: ConceptBoard, analysis: CreativeDirectorAnalysis
    ) -> ConceptBoard:
        # Keep scored winner; optionally boost concepts matching analysis emotion.
        emotion = (analysis.emotion or "").casefold()
        if not emotion:
            return board
        ranked = sorted(board.concepts, key=lambda c: c.scores.overall, reverse=True)
        for concept in ranked:
            if emotion in (concept.emotion or "").casefold():
                if concept.id != board.selected_id:
                    board.selected_id = concept.id
                    board.selected_reason = (
                        f"{board.selected_reason} Also preferred for Creative Director "
                        f"emotion “{analysis.emotion}”."
                    ).strip()
                break
        return board

    @staticmethod
    def _write_artifacts(
        project_dir: Path,
        brief: CreativeBrief,
        analysis: CreativeDirectorAnalysis,
        board: ConceptBoard,
        resolved: Any,
    ) -> None:
        folder = Path(project_dir) / "thumbnail"
        folder.mkdir(parents=True, exist_ok=True)
        # Creative brief snapshot
        brief_payload = {
            "channel_name": brief.channel_name,
            "folder_name": brief.folder_name,
            "general": brief.general.to_dict(),
            "brand": brief.brand.to_dict(),
            "thumbnail": brief.thumbnail.to_dict(),
            "image": brief.image.to_dict(),
            "story": brief.story.to_dict(),
            "personality": brief.personality.to_dict(),
            "goals": brief.goals.to_dict(),
            "project": brief.project.to_dict(),
            "rules": [r.to_dict() for r in brief.enabled_rules],
            "references": [r.to_dict() for r in brief.references],
            "analysis": analysis.to_dict(),
        }
        (folder / "creative_brief.json").write_text(
            json.dumps(brief_payload, indent=2) + "\n", encoding="utf-8"
        )
        del resolved  # metadata already on analysis
        write_concept_board(project_dir, board)
