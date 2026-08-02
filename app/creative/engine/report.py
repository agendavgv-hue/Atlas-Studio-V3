"""Creative Director debug report — saved per project generation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.creative.engine.brief import CreativeBrief


@dataclass
class CreativeDirectorReport:
    channel_name: str
    domain: str
    brand_kit_loaded: str = "NO"
    thumbnail_references_loaded: int = 0
    image_references_loaded: int = 0
    creative_rules_loaded: int = 0
    brand_colors_loaded: str = "NO"
    logo_loaded: str = "NO"
    fonts_loaded: str = "NO"
    thumbnail_style_profile_loaded: str = "NO"
    image_style_profile_loaded: str = "NO"
    master_prompt_generated: str = "NO"
    master_prompt_length: int = 0
    loaded_brand_kit: bool = False
    loaded_thumbnail_dna: bool = False
    loaded_image_dna: bool = False
    loaded_story_dna: bool = False
    loaded_voice_dna: bool = False
    loaded_movie_dna: bool = False
    loaded_music_dna: bool = False
    loaded_creative_rules: int = 0
    loaded_personality: bool = False
    loaded_references: int = 0
    reference_count: int = 0
    generation_started: str = ""
    notes: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "domain": self.domain,
            "Brand Kit Loaded": self.brand_kit_loaded,
            "Thumbnail References Loaded": self.thumbnail_references_loaded,
            "Image References Loaded": self.image_references_loaded,
            "Creative Rules Loaded": self.creative_rules_loaded,
            "Brand Colors Loaded": self.brand_colors_loaded,
            "Logo Loaded": self.logo_loaded,
            "Fonts Loaded": self.fonts_loaded,
            "Thumbnail Style Profile Loaded": self.thumbnail_style_profile_loaded,
            "Image Style Profile Loaded": self.image_style_profile_loaded,
            "Master Prompt Generated": self.master_prompt_generated,
            "Prompt Length": self.master_prompt_length,
            "loaded_brand_kit": self.loaded_brand_kit,
            "loaded_thumbnail_dna": self.loaded_thumbnail_dna,
            "loaded_image_dna": self.loaded_image_dna,
            "loaded_story_dna": self.loaded_story_dna,
            "loaded_voice_dna": self.loaded_voice_dna,
            "loaded_movie_dna": self.loaded_movie_dna,
            "loaded_music_dna": self.loaded_music_dna,
            "loaded_creative_rules": self.loaded_creative_rules,
            "loaded_personality": self.loaded_personality,
            "loaded_references": self.loaded_references,
            "master_prompt_length": self.master_prompt_length,
            "reference_count": self.reference_count,
            "generation_started": self.generation_started,
            "notes": list(self.notes),
            "extras": dict(self.extras),
        }

    @classmethod
    def from_brief(
        cls,
        brief: CreativeBrief,
        *,
        domain: str,
        master_prompt: str = "",
        thumbnail_profile_loaded: bool = False,
        image_profile_loaded: bool = False,
    ) -> CreativeDirectorReport:
        thumb_refs = next(
            (r.count for r in brief.references if r.kind == "thumbnails"), 0
        )
        image_refs = next((r.count for r in brief.references if r.kind == "images"), 0)
        colors_ok = bool(
            brief.brand.primary_color
            or brief.brand.secondary_color
            or brief.brand.accent_color
        )
        logo_ok = bool(brief.brand.logo or brief.brand.thumbnail_logo)
        fonts_ok = bool(brief.brand.fonts)
        prompt_ok = bool((master_prompt or "").strip())
        return cls(
            channel_name=brief.channel_name,
            domain=domain,
            brand_kit_loaded="YES",
            thumbnail_references_loaded=thumb_refs,
            image_references_loaded=image_refs,
            creative_rules_loaded=len(brief.enabled_rules),
            brand_colors_loaded="YES" if colors_ok else "NO",
            logo_loaded="YES" if logo_ok else "NO",
            fonts_loaded="YES" if fonts_ok else "NO",
            thumbnail_style_profile_loaded="YES" if thumbnail_profile_loaded else "NO",
            image_style_profile_loaded="YES" if image_profile_loaded else "NO",
            master_prompt_generated="YES" if prompt_ok else "NO",
            master_prompt_length=len(master_prompt or ""),
            loaded_brand_kit=True,
            loaded_thumbnail_dna=True,
            loaded_image_dna=True,
            loaded_story_dna=True,
            loaded_voice_dna=True,
            loaded_movie_dna=True,
            loaded_music_dna=True,
            loaded_creative_rules=len(brief.enabled_rules),
            loaded_personality=bool(brief.personality.traits),
            loaded_references=brief.reference_count,
            reference_count=brief.reference_count,
            generation_started=datetime.now(timezone.utc).isoformat(),
        )


def write_report(project_dir: Path, report: CreativeDirectorReport) -> Path:
    folder = Path(project_dir) / "creative_director"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = folder / f"report_{report.domain}_{stamp}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    latest = folder / f"latest_{report.domain}.json"
    latest.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path
