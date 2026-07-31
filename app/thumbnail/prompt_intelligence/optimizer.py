"""Prompt optimizer — strip filler, buzzwords, duplicates. No AI calls."""

from __future__ import annotations

import re

# Empty marketing adjectives → drop (or replace with concrete visuals).
FILLER_ADJECTIVES = {
    "stunning",
    "beautiful",
    "amazing",
    "incredible",
    "epic",
    "awesome",
    "gorgeous",
    "magnificent",
    "breathtaking",
    "mind-blowing",
    "mindblowing",
    "perfect",
    "ultimate",
    "legendary",
}

# Generic AI sludge that weakens professional prompts.
AI_BUZZWORDS = {
    "masterpiece",
    "best quality",
    "ultra detailed",
    "ultra-detailed",
    "highly detailed",
    "8k",
    "4k",
    "16k",
    "uhd",
    "hdr",
    "trending on artstation",
    "artstation",
    "concept art",
    "octane render",
    "unreal engine",
    "cinematic lighting masterpiece",
    "award winning",
    "award-winning",
    "hyperrealistic",
    "hyper realistic",
    "super detailed",
    "intricate details",
    "insanely detailed",
}

_MULTI_SPACE = re.compile(r"\s+")
_MULTI_PUNCT = re.compile(r"([,.!;:])\1+")
_COMMA_SPACE = re.compile(r"\s*,\s*")


def optimize_text(text: str, *, max_words: int | None = None) -> str:
    """Clean one block: buzzwords, filler, duplicates, excess punctuation."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    lowered = cleaned.casefold()
    for phrase in sorted(AI_BUZZWORDS, key=len, reverse=True):
        if phrase in lowered:
            cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.IGNORECASE)
            lowered = cleaned.casefold()

    tokens = re.findall(r"[A-Za-z0-9_'+-]+|[^\sA-Za-z0-9]", cleaned)
    kept: list[str] = []
    seen_words: set[str] = set()
    for token in tokens:
        if token.isspace():
            continue
        if re.fullmatch(r"[A-Za-z0-9_'+-]+", token):
            word_key = token.casefold()
            if word_key in FILLER_ADJECTIVES:
                continue
            if word_key in seen_words and word_key not in {
                "and",
                "or",
                "the",
                "a",
                "an",
                "of",
                "in",
                "on",
                "to",
                "for",
                "with",
                "from",
            }:
                continue
            seen_words.add(word_key)
            kept.append(token)
        else:
            kept.append(token)

    rebuilt = _join_tokens(kept)
    rebuilt = _MULTI_PUNCT.sub(r"\1", rebuilt)
    rebuilt = _COMMA_SPACE.sub(", ", rebuilt)
    rebuilt = _MULTI_SPACE.sub(" ", rebuilt).strip(" ,.;:")

    if max_words is not None and max_words > 0:
        words = rebuilt.split()
        if len(words) > max_words:
            rebuilt = " ".join(words[:max_words]).rstrip(" ,.;:")

    return rebuilt.strip()


def optimize_negative(text: str) -> str:
    """Deduplicate comma-separated negative terms."""
    parts = [part.strip() for part in (text or "").split(",")]
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        if not part:
            continue
        key = part.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(part)
    return ", ".join(ordered)


def _join_tokens(tokens: list[str]) -> str:
    if not tokens:
        return ""
    out: list[str] = []
    for token in tokens:
        if not out:
            out.append(token)
            continue
        if re.fullmatch(r"[,.;:!?'\"]+", token):
            out[-1] = out[-1].rstrip() + token
        else:
            out.append(" " + token)
    return "".join(out).strip()
