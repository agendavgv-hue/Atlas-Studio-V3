"""Shared progress payload for voice generation UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceQueueProgress:
    current: int
    total: int
    message: str
    detail: str = ""
    elapsed_seconds: float = 0.0

    @property
    def short_detail(self) -> str:
        text = (self.detail or "").strip()
        if len(text) <= 80:
            return text
        return text[:77] + "…"
