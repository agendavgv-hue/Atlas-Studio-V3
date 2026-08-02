"""Thumbnail Pipeline V3 debug report — thumbnail_debug.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.creative.engine.brief import CreativeBrief
from app.thumbnail.pipeline.critic_scores import ThumbnailCriticScores
from app.thumbnail.pipeline.plan import ThumbnailPlan
from app.thumbnail.pipeline.reference_compare import ReferenceSimilarityReport


@dataclass
class ThumbnailDebugReport:
    channel_name: str = ""
    thumbnail_plan: dict[str, Any] = field(default_factory=dict)
    creative_brief: dict[str, Any] = field(default_factory=dict)
    prompt: str = ""
    reference_count: int = 0
    similarity_score: float = 0.0
    critic_score: float = 0.0
    final_score: float = 0.0
    critic: dict[str, Any] = field(default_factory=dict)
    similarity: dict[str, Any] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    approved: bool = False
    generated_at: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Sprint-facing keys
        payload["Thumbnail Plan"] = self.thumbnail_plan
        payload["Creative Brief"] = self.creative_brief
        payload["Prompt"] = self.prompt
        payload["Reference Count"] = self.reference_count
        payload["Similarity Score"] = self.similarity_score
        payload["Critic Score"] = self.critic_score
        payload["Final Score"] = self.final_score
        return payload


def build_debug_report(
    *,
    brief: CreativeBrief,
    plan: ThumbnailPlan,
    prompt: str,
    similarity: ReferenceSimilarityReport,
    critic: ThumbnailCriticScores,
    attempts: list[dict[str, Any]] | None = None,
) -> ThumbnailDebugReport:
    brief_summary = {
        "channel_name": brief.channel_name,
        "folder_name": brief.folder_name,
        "brand_colors": [
            c
            for c in (
                brief.brand.primary_color,
                brief.brand.secondary_color,
                brief.brand.accent_color,
            )
            if c
        ],
        "logo": bool(brief.brand.thumbnail_logo or brief.brand.logo),
        "frame": bool(getattr(brief.brand, "thumbnail_frame", "")),
        "fonts": list(brief.brand.fonts),
        "rules": len(brief.enabled_rules),
        "references": [r.to_dict() for r in brief.references],
        "personality_traits": {
            k: v for k, v in brief.personality.traits.items() if v >= 70
        },
        "goals": brief.goals.to_dict() if hasattr(brief.goals, "to_dict") else {},
        "project": brief.project.to_dict(),
    }
    return ThumbnailDebugReport(
        channel_name=brief.channel_name,
        thumbnail_plan=plan.to_dict(),
        creative_brief=brief_summary,
        prompt=prompt,
        reference_count=similarity.reference_count,
        similarity_score=similarity.similarity_score,
        critic_score=critic.overall,
        final_score=critic.overall,
        critic=critic.to_dict(),
        similarity=similarity.to_dict(),
        attempts=list(attempts or []),
        approved=critic.approved,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def write_thumbnail_debug(path: Path, report: ThumbnailDebugReport) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path
