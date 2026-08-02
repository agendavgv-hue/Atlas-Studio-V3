"""AI role identifiers for the Orchestrator."""

from __future__ import annotations

from enum import Enum


class AIRole(str, Enum):
    """Specialized Atlas roles — each can bind a different provider/model."""

    CREATIVE_DIRECTOR = "creative_director"
    IMAGE_GENERATOR = "image_generator"
    CRITIC = "critic"
    SEO = "seo"
    STORY = "story"
    DEFAULT_TEXT = "default_text"


TEXT_ROLES: tuple[AIRole, ...] = (
    AIRole.CREATIVE_DIRECTOR,
    AIRole.CRITIC,
    AIRole.SEO,
    AIRole.STORY,
    AIRole.DEFAULT_TEXT,
)

IMAGE_ROLES: tuple[AIRole, ...] = (AIRole.IMAGE_GENERATOR,)

ROLE_LABELS: dict[AIRole, str] = {
    AIRole.CREATIVE_DIRECTOR: "Creative Director",
    AIRole.IMAGE_GENERATOR: "Image Generator",
    AIRole.CRITIC: "Critic",
    AIRole.SEO: "SEO",
    AIRole.STORY: "Story",
    AIRole.DEFAULT_TEXT: "Default Text",
}
