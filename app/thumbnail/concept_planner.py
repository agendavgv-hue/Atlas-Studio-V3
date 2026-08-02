"""Legacy concept planner API — delegates scoring path where possible.

Prefer ``app.thumbnail.concepts.ThumbnailConceptPlanner`` for Pipeline V3.
This module keeps ConceptPlan / ThumbnailConcept for older intelligence callers.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.models.thumbnail_dna import ThumbnailDNA
from app.providers.base import TextProvider
from app.providers.errors import ProviderError
from app.thumbnail.text_utils import parse_json_object
from app.thumbnail.thumbnail_director import ThumbnailStrategy

_SYSTEM = (
    "You are Atlas Studio's Thumbnail Concept Director. "
    "You maximize click-through rate. Think first — never write an image prompt. "
    "Pick the highest-click scene, invent five distinct concepts, then choose one."
)

_USER = """Channel: {channel}

Channel DNA (identity):
{channel_dna}

Thumbnail DNA (learned style — follow layout/colors/emotion, not story content):
{thumbnail_dna}

Script:
---
{script}
---

Production sheet (optional scene inventory):
---
{sheet}
---

Steps (do all in one JSON response):
1. Select the scene with the highest click value.
2. Invent exactly 5 thumbnail concepts (short titles + one-line visual idea).
3. Choose the single best concept for CTR.

Return ONLY JSON:
{{
  "selected_scene": "scene description from script/sheet",
  "click_value_reason": "why this scene wins",
  "concepts": [
    {{"id": 1, "title": "short title", "idea": "one line visual"}},
    {{"id": 2, "title": "short title", "idea": "one line visual"}},
    {{"id": 3, "title": "short title", "idea": "one line visual"}},
    {{"id": 4, "title": "short title", "idea": "one line visual"}},
    {{"id": 5, "title": "short title", "idea": "one line visual"}}
  ],
  "chosen_concept_id": 1,
  "chosen_reason": "why this concept wins",
  "emotion": "Mystery|Shock|Fear|Discovery|Wonder|Curiosity|Urgency|Awe|Suspense",
  "hero_subject": "single iconic visual subject",
  "click_reason": "one sentence CTR hook reason",
  "dominant_feeling": "short viewer gut reaction"
}}
"""


@dataclass(frozen=True)
class ThumbnailConcept:
    id: int
    title: str
    idea: str


@dataclass(frozen=True)
class ConceptPlan:
    """Result of think → choose before prompt writing."""

    selected_scene: str
    click_value_reason: str
    concepts: tuple[ThumbnailConcept, ...]
    chosen: ThumbnailConcept
    chosen_reason: str
    strategy: ThumbnailStrategy
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "selected_scene": self.selected_scene,
            "click_value_reason": self.click_value_reason,
            "concepts": [asdict(c) for c in self.concepts],
            "chosen_concept_id": self.chosen.id,
            "chosen_reason": self.chosen_reason,
            "strategy": self.strategy.to_dict(),
            "extras": dict(self.extras),
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


class ThumbnailConceptPlanner:
    """AI step: scene → 5 concepts → pick best (no image prompt yet).

    Legacy entry used by Thumbnail Intelligence. Pipeline V3 uses
    ``app.thumbnail.concepts.ThumbnailConceptPlanner`` instead.
    """

    def __init__(self, text_provider: TextProvider) -> None:
        self._text = text_provider

    def plan(
        self,
        *,
        script_text: str,
        channel_name: str = "",
        sheet_text: str = "",
        channel_dna_text: str = "",
        thumbnail_dna: ThumbnailDNA | None = None,
    ) -> ConceptPlan:
        script = (script_text or "").strip()
        if not script:
            raise ProviderError("Script is empty — cannot plan thumbnail concepts.")

        thumb_block = (
            thumbnail_dna.prompt_block()
            if thumbnail_dna is not None
            else "No Thumbnail DNA yet — use strong general CTR composition."
        )
        prompt = _USER.format(
            channel=(channel_name or "Unknown").strip() or "Unknown",
            channel_dna=(channel_dna_text or "No Channel DNA provided.").strip(),
            thumbnail_dna=thumb_block,
            script=script[:10000],
            sheet=(sheet_text or "No production sheet.").strip()[:6000],
        )
        raw = self._text.generate_text(prompt, system=_SYSTEM)
        data = parse_json_object(raw, label="Thumbnail Concept Planner")
        return _plan_from_mapping(data)


def _plan_from_mapping(data: dict) -> ConceptPlan:
    concepts_raw = data.get("concepts") if isinstance(data.get("concepts"), list) else []
    concepts: list[ThumbnailConcept] = []
    for i, item in enumerate(concepts_raw[:5], start=1):
        if not isinstance(item, dict):
            continue
        concepts.append(
            ThumbnailConcept(
                id=int(item.get("id") or i),
                title=str(item.get("title") or f"Concept {i}").strip(),
                idea=str(item.get("idea") or "").strip(),
            )
        )
    while len(concepts) < 5:
        n = len(concepts) + 1
        concepts.append(ThumbnailConcept(id=n, title=f"Concept {n}", idea=""))

    try:
        chosen_id = int(data.get("chosen_concept_id") or concepts[0].id)
    except (TypeError, ValueError):
        chosen_id = concepts[0].id
    chosen = next((c for c in concepts if c.id == chosen_id), concepts[0])

    hero = str(data.get("hero_subject") or chosen.idea or chosen.title).strip()
    strategy = ThumbnailStrategy(
        emotion=str(data.get("emotion") or "Curiosity").strip() or "Curiosity",
        click_reason=str(data.get("click_reason") or data.get("chosen_reason") or "").strip()
        or f"Click for: {chosen.title}",
        hero_subject=hero,
        dominant_feeling=str(data.get("dominant_feeling") or "").strip(),
        rationale=str(data.get("chosen_reason") or data.get("click_value_reason") or "").strip(),
    )
    return ConceptPlan(
        selected_scene=str(data.get("selected_scene") or "").strip(),
        click_value_reason=str(data.get("click_value_reason") or "").strip(),
        concepts=tuple(concepts),
        chosen=chosen,
        chosen_reason=str(data.get("chosen_reason") or "").strip(),
        strategy=strategy,
    )
