"""ThumbnailPlanner — think → 3 concepts → choose (no image generation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.providers.base import TextProvider
from app.thumbnail.concept_planner import ConceptPlan, ThumbnailConceptPlanner
from app.thumbnail.intelligence.context import ThumbnailIntelligenceContext


@dataclass(frozen=True)
class ThumbnailPlan:
    """Planner output before prompt writing."""

    concept_plan: ConceptPlan
    intelligence_brief: str
    selected_scene: str
    chosen_title: str

    @property
    def strategy(self):
        return self.concept_plan.strategy


class ThumbnailPlanner:
    """Design-time planner: script/sheet + Creative Director + DNA → best concept."""

    def __init__(self, text_provider: TextProvider) -> None:
        self._concepts = ThumbnailConceptPlanner(text_provider)

    def plan(
        self,
        *,
        script_text: str,
        sheet_text: str = "",
        channel_name: str = "",
        channel_dna_text: str = "",
        intelligence: ThumbnailIntelligenceContext | None = None,
        thumbnail_dna: Any | None = None,
    ) -> ThumbnailPlan:
        brief = ""
        dna = thumbnail_dna
        if intelligence is not None:
            brief = intelligence.identity_brief()
            dna = intelligence.dna or thumbnail_dna
            # Prefer studio max words in DNA typography when present
            if dna is not None and hasattr(dna, "typography"):
                try:
                    dna.typography.max_words = intelligence.studio.max_words
                except Exception:  # noqa: BLE001
                    pass

        channel_block = (channel_dna_text or "").strip()
        if brief:
            channel_block = f"{channel_block}\n\nTHUMBNAIL INTELLIGENCE:\n{brief}".strip()

        concept = self._concepts.plan(
            script_text=script_text,
            channel_name=channel_name,
            sheet_text=sheet_text,
            channel_dna_text=channel_block,
            thumbnail_dna=dna,
        )
        return ThumbnailPlan(
            concept_plan=concept,
            intelligence_brief=brief,
            selected_scene=concept.selected_scene,
            chosen_title=concept.chosen.title,
        )
