"""Shared progress payload for image queue UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageQueueProgress:
    current: int
    total: int
    message: str
    prompt: str = ""
    elapsed_seconds: float = 0.0

    @property
    def short_prompt(self) -> str:
        text = (self.prompt or "").strip()
        if len(text) <= 80:
            return text
        return text[:77] + "…"
