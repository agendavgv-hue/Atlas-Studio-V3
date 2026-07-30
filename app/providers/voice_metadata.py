"""Provider-agnostic voice catalogue metadata helpers."""

from __future__ import annotations

from app.providers.voice_base import VoiceInfo


def display_name_from_id(voice_id: str) -> str:
    """Human label from an opaque voice id (e.g. ``af_heart`` → ``Heart``)."""
    raw = (voice_id or "").strip()
    if not raw:
        return ""
    if "_" in raw:
        return raw.split("_", 1)[1].replace("_", " ").title()
    return raw.replace("-", " ").title()


def enrich_voice_info(
    voice: VoiceInfo,
    *,
    gender: str = "",
    accent: str = "",
    age: str = "",
    style_tags: tuple[str, ...] | list[str] = (),
    sample_text: str = "",
) -> VoiceInfo:
    """Return a copy with catalogue metadata filled in where missing."""
    tags = tuple(tag.strip() for tag in style_tags if str(tag).strip())
    return VoiceInfo(
        voice_id=voice.voice_id,
        name=voice.name or display_name_from_id(voice.voice_id),
        language=voice.language,
        description=voice.description,
        gender=gender or voice.gender,
        accent=accent or voice.accent,
        age=age or voice.age,
        style_tags=tags or voice.style_tags,
        sample_text=sample_text or voice.sample_text,
    )


def score_voice_match(
    voice: VoiceInfo,
    *,
    gender: str = "",
    style_tags: tuple[str, ...] | list[str] = (),
    language: str = "",
) -> int:
    """Higher is better. Used to auto-pick a channel narrator."""
    score = 0
    wanted_gender = (gender or "").strip().casefold()
    if wanted_gender and voice.gender.strip().casefold() == wanted_gender:
        score += 100
    elif wanted_gender and voice.gender:
        score -= 40

    wanted_lang = (language or "").strip().casefold()
    voice_lang = (voice.language or "").strip().casefold()
    if wanted_lang and voice_lang:
        if wanted_lang == voice_lang or wanted_lang[:2] == voice_lang[:2]:
            score += 20

    wanted_styles = {tag.strip().casefold() for tag in style_tags if str(tag).strip()}
    if wanted_styles:
        have = {tag.casefold() for tag in voice.style_tags}
        score += 12 * len(wanted_styles & have)

    return score


def select_closest_voice(
    voices: list[VoiceInfo],
    *,
    gender: str = "",
    style_tags: tuple[str, ...] | list[str] = (),
    language: str = "",
) -> VoiceInfo | None:
    if not voices:
        return None
    ranked = sorted(
        voices,
        key=lambda item: (
            score_voice_match(
                item, gender=gender, style_tags=style_tags, language=language
            ),
            item.name.casefold(),
        ),
        reverse=True,
    )
    return ranked[0]


PREFERRED_VOICE_MISSING_WARNING = (
    "Preferred voice not available. Using closest match."
)


def resolve_available_voice(
    voices: list[VoiceInfo],
    *,
    preferred_voice_id: str = "",
    gender: str = "",
    style_tags: tuple[str, ...] | list[str] = (),
    language: str = "",
) -> tuple[VoiceInfo | None, str]:
    """Return the preferred voice, or the closest match when it is missing.

    Never fails when the catalogue has at least one voice.
    """
    if not voices:
        return None, "No voices available."

    preferred = (preferred_voice_id or "").strip()
    if preferred:
        for voice in voices:
            if voice.voice_id == preferred:
                return voice, ""

    match = select_closest_voice(
        voices,
        gender=gender,
        style_tags=style_tags,
        language=language,
    )
    if match is None:
        return None, "No voices available."
    if preferred:
        return match, PREFERRED_VOICE_MISSING_WARNING
    return match, ""
