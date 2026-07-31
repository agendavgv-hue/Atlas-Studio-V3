"""Shared text helpers for the Thumbnail Engine AI steps."""

from __future__ import annotations

import json
import re

from app.providers.errors import ProviderError

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")
HOOK_MAX_WORDS = 5


def parse_json_object(raw: str, *, label: str = "Thumbnail AI") -> dict:
    text = (raw or "").strip()
    if not text:
        raise ProviderError(f"{label} returned empty text.")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(text)
    if match is None:
        raise ProviderError(f"{label} did not return JSON.")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ProviderError(f"{label} JSON is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise ProviderError(f"{label} JSON must be an object.")
    return data


def normalize_hook(raw: str) -> str:
    cleaned = " ".join((raw or "").replace("\n", " ").split()).strip()
    cleaned = cleaned.strip("\"'`")
    if not cleaned:
        return ""
    words = cleaned.split()
    if len(words) > HOOK_MAX_WORDS:
        words = words[:HOOK_MAX_WORDS]
    return " ".join(words).upper()
