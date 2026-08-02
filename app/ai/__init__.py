"""AI Orchestrator package — Atlas routes specialized AIs per role."""

from app.ai.orchestrator import AIOrchestratorService, ResolvedAI, try_text_with_fallback
from app.ai.roles import AIRole, ROLE_LABELS
from app.ai.settings import AIOrchestratorSettings, RoleBinding

__all__ = [
    "AIOrchestratorService",
    "AIOrchestratorSettings",
    "AIRole",
    "ROLE_LABELS",
    "ResolvedAI",
    "RoleBinding",
    "try_text_with_fallback",
]
