"""Creative Director Framework — identity guardian for Atlas Studio channels.

Runtime generation goes through::

    from app.creative.engine import CreativeDirectorEngine
    brief = CreativeDirectorEngine(data_root).build_brief(channel)
"""

from app.creative.models import (
    BrandKit,
    CreativeDirector,
    CreativeRule,
    StyleLibrary,
    default_rules,
)
from app.creative.services import CreativeDirectorService, ReferenceLibrary
from app.creative.critic import (
    CriticDomain,
    CriticReport,
    CriticRule as CriticEvalRule,
    CriticScore,
    CriticService,
)

__all__ = [
    "BrandKit",
    "CreativeDirector",
    "CreativeDirectorService",
    "CreativeRule",
    "CriticDomain",
    "CriticEvalRule",
    "CriticReport",
    "CriticScore",
    "CriticService",
    "ReferenceLibrary",
    "StyleLibrary",
    "default_rules",
]
