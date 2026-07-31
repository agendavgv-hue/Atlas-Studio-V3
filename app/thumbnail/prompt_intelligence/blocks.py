"""Structured prompt blocks ordered by visual priority."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# Visual priority (higher first). Small decoration is intentionally omitted
# from thumbnail prompts — it only hurts CTR.
BLOCK_PRIORITY: dict[str, int] = {
    "subject": 10,
    "lighting": 9,
    "composition": 9,
    "mood": 8,
    "camera": 7,
    "environment": 6,
    "materials": 5,
    "style": 5,
    "color_palette": 4,
    "quality": 3,
    "negative_prompt": 0,
}

ASSEMBLY_ORDER: tuple[str, ...] = (
    "subject",
    "lighting",
    "composition",
    "mood",
    "camera",
    "environment",
    "materials",
    "style",
    "color_palette",
    "quality",
)


@dataclass
class PromptBlocks:
    """Fixed professional prompt blocks — never one unstructured blob."""

    subject: str = ""
    environment: str = ""
    lighting: str = ""
    composition: str = ""
    camera: str = ""
    mood: str = ""
    style: str = ""
    materials: str = ""
    color_palette: str = ""
    quality: str = ""
    negative_prompt: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def ordered_positive_items(self) -> list[tuple[str, str]]:
        """Return (name, text) pairs in visual-priority assembly order."""
        mapping = {
            "subject": self.subject,
            "lighting": self.lighting,
            "composition": self.composition,
            "mood": self.mood,
            "camera": self.camera,
            "environment": self.environment,
            "materials": self.materials,
            "style": self.style,
            "color_palette": self.color_palette,
            "quality": self.quality,
        }
        items: list[tuple[str, str]] = []
        for name in ASSEMBLY_ORDER:
            text = " ".join(str(mapping.get(name) or "").split()).strip()
            if text:
                items.append((name, text))
        return items
