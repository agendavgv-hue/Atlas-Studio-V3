"""Thumbnail Director — creative CTR strategy before hero/hook/prompt.

A thumbnail is a marketing tool. This step decides emotion and click reason
before any image prompt is written.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.providers.base import TextProvider
from app.providers.errors import ProviderError
from app.thumbnail.text_utils import parse_json_object

ALLOWED_EMOTIONS = (
    "Mystery",
    "Shock",
    "Fear",
    "Discovery",
    "Wonder",
    "Curiosity",
    "Urgency",
    "Awe",
    "Suspense",
)


@dataclass(frozen=True)
class ThumbnailStrategy:
    """Creative decision package written to ``thumbnail_strategy.json``."""

    emotion: str
    click_reason: str
    hero_subject: str
    dominant_feeling: str = ""
    rationale: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


_SYSTEM = (
    "You are a world-class YouTube Thumbnail Director. "
    "Your only goal is maximum click-through rate. "
    "A thumbnail is NOT a pretty picture — it is a marketing weapon. "
    "You decide emotion and click motive BEFORE any image prompt."
)

_USER_TEMPLATE = """Read this full YouTube script and decide the thumbnail STRATEGY.

Channel: {channel_name}

Script:
---
{script}
---

Do NOT write an image prompt.
Do NOT write a video title.

Return ONLY valid JSON:
{{
  "emotion": one of {emotions},
  "click_reason": one sentence — why a stranger must click right now,
  "hero_subject": the single most iconic visual from the script
    (the image someone would still remember in six months).
    If several heroes are possible, pick the one that creates the MOST curiosity.
    Never a generic topic. Never a random object.
  "dominant_feeling": short phrase for the viewer gut reaction,
  "rationale": one sentence explaining the CTR decision
}}

JSON only. No markdown.
"""


class ThumbnailDirector:
    """First AI step: emotion + click reason + preferred hero subject."""

    def __init__(self, text_provider: TextProvider) -> None:
        self._text = text_provider

    def direct(self, script_text: str, *, channel_name: str = "") -> ThumbnailStrategy:
        script = (script_text or "").strip()
        if not script:
            raise ProviderError("Script is empty — cannot direct a thumbnail.")

        prompt = _USER_TEMPLATE.format(
            channel_name=(channel_name or "Unknown").strip() or "Unknown",
            script=script[:12000],
            emotions=", ".join(ALLOWED_EMOTIONS),
        )
        try:
            raw = self._text.generate_text(prompt, system=_SYSTEM)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Thumbnail director failed: {exc}") from exc

        data = parse_json_object(raw, label="Thumbnail director")
        emotion = _normalize_emotion(str(data.get("emotion") or ""))
        click_reason = str(data.get("click_reason") or "").strip()
        hero = str(data.get("hero_subject") or "").strip()
        feeling = str(data.get("dominant_feeling") or "").strip()
        rationale = str(data.get("rationale") or "").strip()
        if not emotion:
            raise ProviderError("Thumbnail director returned no emotion.")
        if not click_reason:
            raise ProviderError("Thumbnail director returned no click_reason.")
        if not hero:
            raise ProviderError("Thumbnail director returned no hero_subject.")
        return ThumbnailStrategy(
            emotion=emotion,
            click_reason=click_reason,
            hero_subject=hero,
            dominant_feeling=feeling or emotion,
            rationale=rationale,
        )


def _normalize_emotion(raw: str) -> str:
    cleaned = (raw or "").strip()
    if not cleaned:
        return ""
    for emotion in ALLOWED_EMOTIONS:
        if cleaned.casefold() == emotion.casefold():
            return emotion
    lowered = cleaned.casefold()
    for emotion in ALLOWED_EMOTIONS:
        if emotion.casefold() in lowered:
            return emotion
    return cleaned.title()
