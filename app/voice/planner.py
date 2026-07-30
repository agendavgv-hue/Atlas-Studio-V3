"""VoicePlanner — turn script text into a VoicePlan.

Never calls a provider, synthesizes audio, exports files, or writes manifests.
Sprint 11 defaults to one full-script segment; the plan always exposes
``segments`` as an ordered list (tuple) for future multi-segment planning.
Planning is deterministic for the same script + settings.
"""

from __future__ import annotations

from app.core.voice_settings import VoiceSettings
from app.voice.plan import VoicePlan, VoiceSegment

# Narration estimate — fixed so the same inputs always yield the same duration.
_WORDS_PER_MINUTE = 150.0
_MIN_DURATION_SEC = 0.1


class VoicePlanner:
    """Transforms narration script into an immutable VoicePlan."""

    def __init__(self, settings: VoiceSettings | None = None) -> None:
        self._settings = settings or VoiceSettings()

    def plan(self, script: str) -> VoicePlan:
        """Return a VoicePlan with ordered segments (length >= 1).

        Sprint 11 always produces exactly one segment containing the full script.
        Placeholder fields (pause / emphasis / emotion / speaker) are reserved
        and left at defaults for future planners.

        Raises:
            ValueError: if ``script`` is empty or whitespace-only.
        """
        text = str(script or "").strip()
        if not text:
            raise ValueError("Cannot plan narration from an empty script.")

        language = str(self._settings.language or "en-US").strip() or "en-US"
        speed = float(self._settings.speed or 1.0)
        if speed <= 0:
            speed = 1.0

        estimated = _estimate_duration_sec(text, speed=speed)
        segment = VoiceSegment(
            index=1,
            text=text,
            pause_after_sec=0.0,
            emphasis="",
            emotion="",
            speaker="",
        )
        return VoicePlan(
            segments=(segment,),
            language=language,
            estimated_duration_sec=estimated,
            rationale=_rationale(word_count=_word_count(text)),
        )


def _word_count(text: str) -> int:
    return len(text.split())


def _estimate_duration_sec(text: str, *, speed: float) -> float:
    """Deterministic duration estimate from word count and playback speed."""
    words = max(1, _word_count(text))
    seconds = (words / _WORDS_PER_MINUTE) * 60.0 / speed
    return round(max(_MIN_DURATION_SEC, seconds), 3)


def _rationale(word_count: int) -> str:
    return (
        "Single full-script narration segment "
        f"({word_count} word{'s' if word_count != 1 else ''}; Sprint 11 default)."
    )
