"""Thumbnail Memory — durable learning records for every generated run.

Stores hero, emotion, hook, composition, DNA, prompt, seed, model, LoRAs,
and negatives so Atlas can learn channel identity over time.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MEMORY_VERSION = 1


@dataclass
class ThumbnailMemoryVariant:
    """One generated variant inside a memory record."""

    variant_id: str
    variant_key: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    seed: int = -1
    model: str = ""
    loras: list[str] = field(default_factory=list)
    provider_id: str = ""
    width: int = 0
    height: int = 0
    file_name: str = ""
    critique: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ThumbnailMemoryRecord:
    """Full creative + technical snapshot of one thumbnail run."""

    version: int = MEMORY_VERSION
    channel_name: str = ""
    project_name: str = ""
    created_at: str = ""
    hero_subject: str = ""
    emotion: str = ""
    click_reason: str = ""
    hook: str = ""
    composition: dict[str, Any] = field(default_factory=dict)
    channel_dna: dict[str, Any] = field(default_factory=dict)
    primary_prompt: str = ""
    negative_prompt: str = ""
    seed: int = -1
    model: str = ""
    loras: list[str] = field(default_factory=list)
    primary_variant_id: str = "A"
    selection_method: str = "settings_primary"
    critic_ready: bool = True
    critic_result: dict[str, Any] | None = None
    variants: list[ThumbnailMemoryVariant] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThumbnailMemoryRecord:
        raw = dict(data or {})
        variants_raw = raw.get("variants") if isinstance(raw.get("variants"), list) else []
        variants: list[ThumbnailMemoryVariant] = []
        for item in variants_raw:
            if not isinstance(item, dict):
                continue
            variants.append(
                ThumbnailMemoryVariant(
                    variant_id=str(item.get("variant_id") or ""),
                    variant_key=str(item.get("variant_key") or ""),
                    prompt=str(item.get("prompt") or ""),
                    negative_prompt=str(item.get("negative_prompt") or ""),
                    seed=int(item.get("seed") if item.get("seed") is not None else -1),
                    model=str(item.get("model") or ""),
                    loras=[str(x) for x in (item.get("loras") or [])],
                    provider_id=str(item.get("provider_id") or ""),
                    width=int(item.get("width") or 0),
                    height=int(item.get("height") or 0),
                    file_name=str(item.get("file_name") or ""),
                    critique=dict(item.get("critique") or {}),
                )
            )
        return cls(
            version=int(raw.get("version") or MEMORY_VERSION),
            channel_name=str(raw.get("channel_name") or ""),
            project_name=str(raw.get("project_name") or ""),
            created_at=str(raw.get("created_at") or ""),
            hero_subject=str(raw.get("hero_subject") or ""),
            emotion=str(raw.get("emotion") or ""),
            click_reason=str(raw.get("click_reason") or ""),
            hook=str(raw.get("hook") or ""),
            composition=dict(raw.get("composition") or {}),
            channel_dna=dict(raw.get("channel_dna") or {}),
            primary_prompt=str(raw.get("primary_prompt") or ""),
            negative_prompt=str(raw.get("negative_prompt") or ""),
            seed=int(raw.get("seed") if raw.get("seed") is not None else -1),
            model=str(raw.get("model") or ""),
            loras=[str(x) for x in (raw.get("loras") or [])],
            primary_variant_id=str(raw.get("primary_variant_id") or "A"),
            selection_method=str(raw.get("selection_method") or "settings_primary"),
            critic_ready=bool(raw.get("critic_ready", True)),
            critic_result=raw.get("critic_result")
            if isinstance(raw.get("critic_result"), dict)
            else None,
            variants=variants,
            extras=dict(raw.get("extras") or {}),
        )

    @classmethod
    def read_json(cls, path: Path) -> ThumbnailMemoryRecord:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


class ThumbnailMemoryStore:
    """Write / read ``thumbnail_memory.json`` for learning loops."""

    def save(self, path: Path, record: ThumbnailMemoryRecord) -> Path:
        if not record.created_at:
            record.created_at = datetime.now(timezone.utc).isoformat()
        record.write_json(path)
        return path
