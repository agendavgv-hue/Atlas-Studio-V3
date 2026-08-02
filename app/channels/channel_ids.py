"""Stable filesystem ids for channel-scoped assets (no hardcoded names)."""

from __future__ import annotations

import re

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def channel_id(channel_name: str) -> str:
    """Fold a display/folder name into a cache-safe id (e.g. ``hollow_atlas``)."""
    raw = (channel_name or "").strip()
    if not raw:
        raise ValueError("Channel name is required.")
    cleaned = _INVALID.sub("", raw).strip().casefold()
    slug = _NON_ALNUM.sub("_", cleaned).strip("_")
    if not slug:
        raise ValueError(f"Cannot derive channel id from '{channel_name}'.")
    return slug
