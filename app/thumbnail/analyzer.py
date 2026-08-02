"""Hero subject + curiosity hook — uses Thumbnail Director strategy."""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.base import TextProvider
from app.providers.errors import ProviderError
from app.thumbnail.text_utils import normalize_hook, parse_json_object
from app.thumbnail.thumbnail_director import ThumbnailStrategy


@dataclass(frozen=True)
class ThumbnailAnalysis:
    """Hero + hook chosen for maximum curiosity / CTR."""

    hero_subject: str
    hook: str
    rationale: str = ""


_SYSTEM = (
    "You are a senior YouTube thumbnail copy and subject specialist for premium "
    "documentary and technology channels. You maximize curiosity and clicks. "
    "You never write video titles. Hooks must be 2–5 words, ALL CAPS, punchy, "
    "and designed for Atlas to render as large outlined headline text — not for "
    "the image model to paint."
)

_USER_TEMPLATE = """Using this thumbnail STRATEGY and the script, finalize hero + hook.

Channel: {channel_name}

Strategy (must respect):
- emotion: {emotion}
- click_reason: {click_reason}
- preferred_hero: {preferred_hero}
- dominant_feeling: {feeling}

Script:
---
{script}
---

Rules:
- hero_subject: ONE iconic visual from the script. If multiple options exist,
  choose the one that creates the GREATEST curiosity (not the safest summary).
  Prefer the strategy preferred_hero unless another script image is clearly
  more clickable.
- hook: 2 to 5 words, ALL CAPS, simple, powerful curiosity. NOT a title.
  NOT a summary. Examples: WHO BUILT THIS?, THEY KNEW., IMPOSSIBLE.,
  TOO LATE?, NOT HUMAN?, SECRET FOUND, LOST FOREVER, THE FINAL PROOF

Return ONLY JSON:
{{
  "hero_subject": "...",
  "hook": "...",
  "rationale": "one short CTR sentence"
}}
"""


class ThumbnailAnalyzer:
    """Derive Hero Subject + Thumbnail Hook from strategy + script."""

    def __init__(self, text_provider: TextProvider) -> None:
        self._text = text_provider

    def analyze(
        self,
        script_text: str,
        *,
        strategy: ThumbnailStrategy,
        channel_name: str = "",
    ) -> ThumbnailAnalysis:
        script = (script_text or "").strip()
        if not script:
            raise ProviderError("Script is empty — cannot design a thumbnail.")

        prompt = _USER_TEMPLATE.format(
            channel_name=(channel_name or "Unknown").strip() or "Unknown",
            emotion=strategy.emotion,
            click_reason=strategy.click_reason,
            preferred_hero=strategy.hero_subject,
            feeling=strategy.dominant_feeling or strategy.emotion,
            script=script[:12000],
        )
        try:
            raw = self._text.generate_text(prompt, system=_SYSTEM)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Thumbnail analysis failed: {exc}") from exc

        data = parse_json_object(raw, label="Thumbnail analyzer")
        hero = str(data.get("hero_subject") or strategy.hero_subject or "").strip()
        hook = normalize_hook(str(data.get("hook") or ""))
        rationale = str(data.get("rationale") or "").strip()
        if not hero:
            raise ProviderError("Thumbnail analysis returned no hero_subject.")
        if not hook:
            raise ProviderError("Thumbnail analysis returned no hook.")
        return ThumbnailAnalysis(hero_subject=hero, hook=hook, rationale=rationale)
