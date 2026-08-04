"""Channel content language — first-class multilingual support."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True)
class ChannelLanguage:
    """One supported channel content language."""

    code: str  # ISO-639-1 (en, nl, de, …)
    label: str  # UI label
    locale: str  # BCP-47 for voice / TTS (en-US, nl-NL, …)


# Display order for Channel Settings / Channel Studio dropdowns.
CHANNEL_LANGUAGES: tuple[ChannelLanguage, ...] = (
    ChannelLanguage("en", "English", "en-US"),
    ChannelLanguage("nl", "Dutch", "nl-NL"),
    ChannelLanguage("de", "German", "de-DE"),
    ChannelLanguage("fr", "French", "fr-FR"),
    ChannelLanguage("es", "Spanish", "es-ES"),
    ChannelLanguage("it", "Italian", "it-IT"),
    ChannelLanguage("pt", "Portuguese", "pt-PT"),
    ChannelLanguage("custom", "Custom (future)", "en-US"),
)


def language_choices() -> list[tuple[str, str]]:
    """(label, code) pairs for combo boxes."""
    return [(item.label, item.code) for item in CHANNEL_LANGUAGES]


def normalize_language(value: str | None) -> str:
    """Map free-form / legacy values onto a channel language code."""
    raw = (value or "").strip()
    if not raw:
        return DEFAULT_LANGUAGE
    lowered = raw.casefold().replace("_", "-")
    # Exact code
    for item in CHANNEL_LANGUAGES:
        if lowered == item.code:
            return item.code
    # Locale / prefix (en-US, nl-NL, de, …)
    prefix = lowered.split("-", 1)[0]
    for item in CHANNEL_LANGUAGES:
        if prefix == item.code:
            return item.code
        if lowered == item.locale.casefold():
            return item.code
    # Label match
    for item in CHANNEL_LANGUAGES:
        if lowered == item.label.casefold():
            return item.code
    # Common aliases
    aliases = {
        "english": "en",
        "dutch": "nl",
        "nederlands": "nl",
        "german": "de",
        "deutsch": "de",
        "french": "fr",
        "français": "fr",
        "francais": "fr",
        "spanish": "es",
        "español": "es",
        "espanol": "es",
        "italian": "it",
        "italiano": "it",
        "portuguese": "pt",
        "português": "pt",
        "portugues": "pt",
    }
    if lowered in aliases:
        return aliases[lowered]
    if prefix in aliases:
        return aliases[prefix]
    return DEFAULT_LANGUAGE


def language_label(code: str | None) -> str:
    normalized = normalize_language(code)
    for item in CHANNEL_LANGUAGES:
        if item.code == normalized:
            return item.label
    return "English"


def language_locale(code: str | None) -> str:
    """BCP-47 locale used for voice matching / TTS."""
    normalized = normalize_language(code)
    for item in CHANNEL_LANGUAGES:
        if item.code == normalized:
            return item.locale
    return "en-US"


def is_english(code: str | None) -> bool:
    return normalize_language(code) == "en"


def content_language_instruction(code: str | None) -> str:
    """Prompt block forcing all written content into the channel language."""
    label = language_label(code)
    return (
        f"OUTPUT LANGUAGE: {label}.\n"
        f"Write the ENTIRE output in fluent, natural {label}.\n"
        f"Do not mix other languages unless a proper name has no {label} equivalent.\n"
        f"Titles, narration, descriptions, keywords, and tags must all be in {label}."
    )


def seo_language_instruction(code: str | None) -> str:
    label = language_label(code)
    return (
        f"SEO LANGUAGE: {label}.\n"
        f"Generate the YouTube title, description, keywords, tags, and search phrases "
        f"in fluent {label} for the target audience."
    )


def voice_matches_language(voice_language: str, channel_language: str | None) -> bool:
    """True when a voice catalogue language matches the channel language."""
    wanted = language_locale(channel_language).casefold()
    have = (voice_language or "").strip().casefold()
    if not have:
        # Unknown voice language — keep visible only for English channels.
        return is_english(channel_language)
    if have == wanted or have[:2] == wanted[:2]:
        return True
    # Also accept ISO code alone (nl, de, …)
    code = normalize_language(channel_language)
    return have == code or have.startswith(code + "-")
