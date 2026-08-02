"""AI Critic Framework — judges generator output; never creates content.

Usage::

    from app.creative.critic import CriticService

    report = CriticService(data_root).evaluate(
        channel,
        "thumbnail",
        {"hook": "WHO BUILT THIS?", "prompt": "..."},
        project="P001",
    )
    if not report.approved:
        # generator may regenerate using report.problems
        ...
"""

from app.creative.critic.domains import CriticDomain
from app.creative.critic.report import CriticReport
from app.creative.critic.rules import CriticFinding, CriticRule
from app.creative.critic.score import CriticScore
from app.creative.critic.service import CriticService
from app.creative.critic.settings import CriticSettings

__all__ = [
    "CriticDomain",
    "CriticFinding",
    "CriticReport",
    "CriticRule",
    "CriticScore",
    "CriticService",
    "CriticSettings",
]
