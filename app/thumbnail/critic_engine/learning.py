"""Critic learning — remember what scored high for a channel."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.channels.studio.paths import channel_studio_dir
from app.thumbnail.critic_engine.models import CriticReport

CRITIC_MEMORY_BASENAME = "thumbnail_critic_memory.json"
HIGH_SCORE_FLOOR = 88.0


@dataclass
class CriticMemory:
    channel_name: str = ""
    wins: int = 0
    strong_traits: list[str] = field(default_factory=list)
    average_winning_score: float = 0.0
    last_win_at: str = ""
    trait_counts: dict[str, int] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "wins": self.wins,
            "strong_traits": list(self.strong_traits),
            "average_winning_score": round(self.average_winning_score, 2),
            "last_win_at": self.last_win_at,
            "trait_counts": dict(self.trait_counts),
            "extras": dict(self.extras),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CriticMemory:
        raw = dict(data or {})
        return cls(
            channel_name=str(raw.get("channel_name") or ""),
            wins=int(raw.get("wins") or 0),
            strong_traits=[str(t) for t in (raw.get("strong_traits") or [])],
            average_winning_score=float(raw.get("average_winning_score") or 0),
            last_win_at=str(raw.get("last_win_at") or ""),
            trait_counts={
                str(k): int(v) for k, v in dict(raw.get("trait_counts") or {}).items()
            },
            extras=dict(raw.get("extras") or {}),
        )

    def prompt_hints(self) -> str:
        if not self.strong_traits:
            return ""
        traits = ", ".join(self.strong_traits[:8])
        return (
            "CRITIC LEARNING (traits that scored high for this channel):\n"
            f"- Prefer: {traits}\n"
            f"- Based on {self.wins} high-scoring thumbnail(s)."
        )


class CriticLearningStore:
    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)

    def path_for(self, folder_name: str) -> Path:
        return channel_studio_dir(self._data_root, folder_name) / CRITIC_MEMORY_BASENAME

    def load(self, folder_name: str) -> CriticMemory:
        path = self.path_for(folder_name)
        if not path.is_file():
            return CriticMemory(channel_name=folder_name)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return CriticMemory(channel_name=folder_name)
        return CriticMemory.from_dict(raw if isinstance(raw, dict) else {})

    def save(self, folder_name: str, memory: CriticMemory) -> Path:
        path = self.path_for(folder_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(memory.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    def record_win(
        self,
        folder_name: str,
        report: CriticReport,
        *,
        floor: float = HIGH_SCORE_FLOOR,
    ) -> CriticMemory:
        if report.overall < floor:
            return self.load(folder_name)
        memory = self.load(folder_name)
        strong = [a.axis for a in report.axes if a.score >= floor]
        counts = Counter(memory.trait_counts)
        counts.update(strong)
        memory.trait_counts = {k: int(v) for k, v in counts.items()}
        memory.strong_traits = [k for k, _ in counts.most_common(12)]
        memory.wins += 1
        if memory.wins == 1:
            memory.average_winning_score = report.overall
        else:
            memory.average_winning_score = round(
                (
                    memory.average_winning_score * (memory.wins - 1)
                    + report.overall
                )
                / memory.wins,
                2,
            )
        memory.last_win_at = datetime.now(timezone.utc).isoformat()
        memory.channel_name = folder_name
        self.save(folder_name, memory)
        return memory
