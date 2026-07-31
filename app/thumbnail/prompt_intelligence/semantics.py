"""Semantic contradiction control — rewrite conflicting visual instructions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.thumbnail.prompt_intelligence.blocks import PromptBlocks


@dataclass(frozen=True)
class ContradictionRule:
    name: str
    keep_group: tuple[str, ...]
    drop_group: tuple[str, ...]
    preferred_block: str


# When both sides appear, keep the preferred side and strip the other.
CONTRADICTION_RULES: tuple[ContradictionRule, ...] = (
    ContradictionRule(
        name="framing",
        keep_group=("close-up", "close up", "macro", "tight crop", "medium-close"),
        drop_group=(
            "wide landscape",
            "wide shot",
            "establishing shot",
            "panorama",
            "aerial view",
            "bird's eye",
        ),
        preferred_block="camera",
    ),
    ContradictionRule(
        name="time_of_day",
        keep_group=("night", "midnight", "nocturnal", "moonlit", "after dark"),
        drop_group=("midday", "bright daylight", "noon", "sunny day", "high noon"),
        preferred_block="lighting",
    ),
    ContradictionRule(
        name="visibility",
        keep_group=("fog", "foggy", "mist", "misty", "haze", "atmospheric haze"),
        drop_group=(
            "crystal clear",
            "crystal-clear",
            "perfect visibility",
            "clear skies",
            "razor sharp visibility",
        ),
        preferred_block="environment",
    ),
    ContradictionRule(
        name="busy_vs_clean",
        keep_group=("clean composition", "simple composition", "never busy", "uncluttered"),
        drop_group=("busy scene", "crowded", "chaotic composition", "cluttered"),
        preferred_block="composition",
    ),
)


@dataclass
class SemanticFixReport:
    fixed: list[str]
    blocks: PromptBlocks


def resolve_contradictions(blocks: PromptBlocks) -> SemanticFixReport:
    """Strip conflicting phrases across blocks; prefer higher-priority intent."""
    fixed: list[str] = []
    data = blocks.to_dict()
    # Work on a joined view to detect conflicts, then scrub per-block.
    for rule in CONTRADICTION_RULES:
        joined = " ".join(
            str(data.get(key) or "")
            for key in (
                "subject",
                "environment",
                "lighting",
                "composition",
                "camera",
                "mood",
                "style",
                "materials",
                "color_palette",
                "quality",
            )
        ).casefold()
        has_keep = any(term in joined for term in rule.keep_group)
        has_drop = any(term in joined for term in rule.drop_group)
        if not (has_keep and has_drop):
            # If only drop-side exists without keep, still fine.
            # If only keep exists, fine.
            # Special: if both absent, nothing.
            # If only drop without keep and rule is framing with "wide" conflicting
            # with thumbnail close intent — skip unless both present.
            continue
        # Both present → remove drop_group everywhere except we already prefer keep.
        for field_name in list(data.keys()):
            if field_name in {"negative_prompt", "extras"}:
                continue
            original = str(data.get(field_name) or "")
            scrubbed = original
            for term in rule.drop_group:
                scrubbed = re.sub(
                    re.escape(term),
                    " ",
                    scrubbed,
                    flags=re.IGNORECASE,
                )
            scrubbed = re.sub(r"\s+", " ", scrubbed).strip(" ,.;:")
            if scrubbed != original.strip():
                data[field_name] = scrubbed
                fixed.append(f"{rule.name}: removed conflicting phrasing from {field_name}")

    cleaned = PromptBlocks(
        subject=str(data.get("subject") or ""),
        environment=str(data.get("environment") or ""),
        lighting=str(data.get("lighting") or ""),
        composition=str(data.get("composition") or ""),
        camera=str(data.get("camera") or ""),
        mood=str(data.get("mood") or ""),
        style=str(data.get("style") or ""),
        materials=str(data.get("materials") or ""),
        color_palette=str(data.get("color_palette") or ""),
        quality=str(data.get("quality") or ""),
        negative_prompt=str(data.get("negative_prompt") or ""),
        extras=dict(data.get("extras") or {}),
    )
    return SemanticFixReport(fixed=fixed, blocks=cleaned)
