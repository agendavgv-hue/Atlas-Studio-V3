"""Prompt quality scorer — no AI; scores structure and craft of the prompt itself."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.thumbnail.prompt_intelligence.blocks import ASSEMBLY_ORDER, PromptBlocks
from app.thumbnail.prompt_intelligence.model_profiles import ModelPromptProfile
from app.thumbnail.prompt_intelligence.optimizer import AI_BUZZWORDS, FILLER_ADJECTIVES


@dataclass(frozen=True)
class PromptQualityScore:
    """Scores for how well Atlas wrote the prompt (not the image)."""

    coherence: int = 0
    readability: int = 0
    visualization: int = 0
    originality: int = 0
    channel_dna: int = 0
    model_compatibility: int = 0
    notes: str = ""
    model_profile: str = ""

    @property
    def total(self) -> int:
        values = (
            self.coherence,
            self.readability,
            self.visualization,
            self.originality,
            self.channel_dna,
            self.model_compatibility,
        )
        # Scale 6×0–10 → 0–100
        return max(0, min(100, int(round(sum(values) / 6 * 10))))

    def to_report(self) -> dict:
        return {
            "coherence": self.coherence,
            "readability": self.readability,
            "visualization": self.visualization,
            "originality": self.originality,
            "channel_dna": self.channel_dna,
            "model_compatibility": self.model_compatibility,
            "total": self.total,
            "notes": self.notes,
            "model_profile": self.model_profile,
        }


def score_prompt(
    *,
    prompt: str,
    blocks: PromptBlocks,
    profile: ModelPromptProfile,
    dna_signature: str = "",
    semantic_fixes: list[str] | None = None,
) -> PromptQualityScore:
    text = (prompt or "").strip()
    lowered = text.casefold()
    filled = sum(1 for name in ASSEMBLY_ORDER if getattr(blocks, name, "").strip())

    coherence = _clamp(
        4
        + (3 if filled >= 7 else 0)
        + (2 if not semantic_fixes else 1)
        + (1 if "single" in lowered or "one " in lowered else 0)
    )
    word_count = len(text.split())
    readability = _clamp(
        3
        + (3 if 12 <= word_count <= 90 else 1)
        + (2 if profile.prefer_short_blocks and word_count <= 70 else 1)
        + (2 if ",," not in text and "  " not in text else 0)
    )
    visual_cues = sum(
        1
        for cue in (
            "light",
            "shadow",
            "camera",
            "angle",
            "contrast",
            "depth",
            "focus",
            "material",
            "texture",
            "gold",
            "blue",
            "dark",
        )
        if cue in lowered
    )
    visualization = _clamp(3 + min(5, visual_cues) + (2 if blocks.subject else 0))

    buzz_hits = sum(1 for phrase in AI_BUZZWORDS if phrase in lowered)
    filler_hits = sum(1 for word in FILLER_ADJECTIVES if f" {word} " in f" {lowered} ")
    originality = _clamp(10 - buzz_hits * 2 - filler_hits)

    dna_hit = 0
    if dna_signature and any(
        token and token.casefold() in lowered
        for token in dna_signature.replace(",", " ").split()
        if len(token) > 3
    ):
        dna_hit = 4
    if blocks.color_palette:
        dna_hit += 3
    if blocks.style:
        dna_hit += 2
    channel_dna = _clamp(dna_hit + (1 if blocks.mood else 0))

    sep = (profile.separator or "").strip()
    if profile.use_commas:
        compat = 6 + (2 if ", " in text or text.count(",") >= 3 else 0)
        if text.count(". ") > text.count(", ") + 2:
            compat -= 2
    else:
        compat = 6 + (2 if ". " in text or sep in text else 0)
        if text.count(",") > 12:
            compat -= 2
    if profile.cinematography_bias and "cinematic" in lowered:
        compat += 1
    model_compatibility = _clamp(compat)

    notes = "Prompt Intelligence score (structure + craft)."
    if semantic_fixes:
        notes += f" Semantic fixes: {len(semantic_fixes)}."

    return PromptQualityScore(
        coherence=coherence,
        readability=readability,
        visualization=visualization,
        originality=originality,
        channel_dna=channel_dna,
        model_compatibility=model_compatibility,
        notes=notes,
        model_profile=profile.display_name or profile.key,
    )


def write_prompt_quality_report(path: Path, score: PromptQualityScore, *, blocks: PromptBlocks | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = score.to_report()
    if blocks is not None:
        payload["blocks"] = {
            key: value
            for key, value in blocks.to_dict().items()
            if key != "extras" and str(value or "").strip()
        }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _clamp(value: int) -> int:
    return max(0, min(10, int(value)))
