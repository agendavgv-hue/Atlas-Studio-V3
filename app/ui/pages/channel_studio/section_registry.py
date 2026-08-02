"""Extensible Channel Studio section registry (lazy widget factories)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

SectionFactory = Callable[[], QWidget]


@dataclass(frozen=True)
class SectionSpec:
    key: str
    label: str
    blurb: str = ""
    heavy: bool = False


SECTION_SPECS: tuple[SectionSpec, ...] = (
    SectionSpec("general", "Channel Basics", "Who this channel is", heavy=False),
    SectionSpec("personality", "Personality", "Emotional DNA for all generators", heavy=False),
    SectionSpec("brand", "Brand Kit", "Visual identity assets", heavy=True),
    SectionSpec("thumbnail", "Thumbnail Studio", "Click-stopping instincts", heavy=True),
    SectionSpec("image", "Image Studio", "Look and atmosphere", heavy=True),
    SectionSpec("movie", "Movie Studio", "Motion personality", heavy=True),
    SectionSpec("story", "Story Studio", "Narrative DNA", heavy=False),
    SectionSpec("voice", "Voice Studio", "Narrator personality", heavy=True),
    SectionSpec("music", "Music Studio", "Musical personality", heavy=True),
    SectionSpec("rules", "Creative Rules", "Identity guardrails", heavy=False),
    SectionSpec("goals", "Goals", "Growth targets", heavy=False),
    SectionSpec("advanced", "Advanced", "Storage & diagnostics", heavy=True),
)

SECTION_KEYS: tuple[str, ...] = tuple(spec.key for spec in SECTION_SPECS)

_REF_KIND_BY_SECTION: dict[str, str] = {
    "brand": "branding",
    "thumbnail": "thumbnails",
    "image": "images",
    "movie": "movies",
    "voice": "voices",
    "music": "music",
}


def section_spec(key: str) -> SectionSpec:
    for spec in SECTION_SPECS:
        if spec.key == key:
            return spec
    raise KeyError(key)


def create_section_widget(key: str) -> QWidget:
    """Import and construct a section widget only when first needed."""
    if key == "general":
        from app.ui.pages.channel_studio.sections_a import GeneralSection

        return GeneralSection()
    if key == "personality":
        from app.ui.pages.channel_studio.sections_c import PersonalitySection

        return PersonalitySection()
    if key == "brand":
        from app.ui.pages.channel_studio.sections_a import BrandSection

        return BrandSection()
    if key == "thumbnail":
        from app.ui.pages.channel_studio.sections_a import ThumbnailSection

        return ThumbnailSection()
    if key == "image":
        from app.ui.pages.channel_studio.sections_b import ImageSection

        return ImageSection()
    if key == "movie":
        from app.ui.pages.channel_studio.sections_b import MovieSection

        return MovieSection()
    if key == "story":
        from app.ui.pages.channel_studio.sections_b import StorySection

        return StorySection()
    if key == "voice":
        from app.ui.pages.channel_studio.sections_b import VoiceSection

        return VoiceSection()
    if key == "music":
        from app.ui.pages.channel_studio.sections_b import MusicSection

        return MusicSection()
    if key == "rules":
        from app.ui.pages.channel_studio.sections_c import RulesSection

        return RulesSection()
    if key == "goals":
        from app.ui.pages.channel_studio.sections_c import GoalsSection

        return GoalsSection()
    if key == "advanced":
        from app.ui.pages.channel_studio.sections_c import AdvancedSection

        return AdvancedSection()
    raise KeyError(f"Unknown Channel Studio section: {key}")


def reference_kind_for_section(key: str) -> str | None:
    return _REF_KIND_BY_SECTION.get(key)
