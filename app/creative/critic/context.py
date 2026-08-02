"""Critic evaluation context — Director, Brand, Style, Channel Brain."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.brain.channel_brain import ChannelBrain
from app.brain.service import ChannelBrainService
from app.creative.models.brand_kit import BrandKit
from app.creative.models.director import CreativeDirector
from app.creative.models.style_library import StyleLibrary
from app.creative.services.director_service import CreativeDirectorService


@dataclass
class CriticContext:
    channel: str
    director: CreativeDirector
    brand: BrandKit
    style: StyleLibrary
    brain: ChannelBrain | None = None

    def identity_blob(self) -> str:
        parts = [
            self.director.visual.color_palette,
            self.director.visual.lighting,
            self.director.visual.contrast,
            self.brand.primary_color,
            self.brand.secondary_color,
            self.style.color_palette,
            self.style.lighting,
            self.style.thumbnail_style,
            self.style.story_style,
        ]
        if self.brain is not None:
            parts.append(self.brain.channel_dna.mission)
            parts.append(self.brain.image_dna.prompt_block())
            parts.append(self.brain.thumbnail_dna.prompt_block())
        return " ".join(str(p) for p in parts if p)


def load_critic_context(data_root: Path, channel: str) -> CriticContext:
    creative = CreativeDirectorService(data_root)
    director = creative.ensure(channel)
    brand = creative.get_brand(channel)
    style = creative.get_style(channel)
    brain: ChannelBrain | None = None
    try:
        brains = ChannelBrainService(data_root)
        if brains.exists(channel):
            brain = brains.load(channel)
        else:
            brain = brains.ensure_brain(channel)
    except Exception:  # noqa: BLE001
        brain = None
    return CriticContext(
        channel=channel.strip(),
        director=director,
        brand=brand,
        style=style,
        brain=brain,
    )


def context_as_policy(ctx: CriticContext) -> dict[str, Any]:
    """Flatten identity sources for rule checkers."""
    return {
        "director": ctx.director.to_dict(),
        "brand": ctx.brand.to_dict(),
        "style": ctx.style.to_dict(),
        "brain": ctx.brain.channel_dna.to_dict() if ctx.brain else {},
        "image_dna": ctx.brain.image_dna.to_dict() if ctx.brain else {},
        "thumbnail_dna": ctx.brain.thumbnail_dna.to_dict() if ctx.brain else {},
        "rules": [r.to_dict() for r in ctx.director.enabled_rules()],
        "identity_blob": ctx.identity_blob(),
    }
