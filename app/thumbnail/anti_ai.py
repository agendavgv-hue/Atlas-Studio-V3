"""Anti-AI rules — shared negative list loaded from anti_ai_rules.json.

Never hardcode the forbidden list in engine logic; edit the JSON to evolve it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.storage_paths import StoragePaths


@dataclass(frozen=True)
class AntiAiRules:
    """Global bans that fight generic AI thumbnail sludge."""

    forbidden: tuple[str, ...]
    negative_prompt: str

    def merge_negative(self, *parts: str) -> str:
        chunks: list[str] = []
        seen: set[str] = set()
        for part in (*parts, self.negative_prompt):
            for chunk in str(part or "").split(","):
                cleaned = chunk.strip()
                if not cleaned:
                    continue
                key = cleaned.casefold()
                if key in seen:
                    continue
                seen.add(key)
                chunks.append(cleaned)
        return ", ".join(chunks)


_PACKAGED_PATH = Path(__file__).resolve().parent / "anti_ai_rules.json"


class AntiAiRulesLoader:
    """Resolve ``anti_ai_rules.json`` with override → packaged fallback."""

    def __init__(
        self,
        *,
        data_root: Path | None = None,
        project_root: Path | None = None,
        packaged_path: Path | None = None,
    ) -> None:
        self._data_root = data_root
        self._project_root = project_root
        self._packaged_path = packaged_path or _PACKAGED_PATH

    def candidates(self) -> list[Path]:
        paths: list[Path] = []
        if self._project_root is not None:
            paths.append(Path(self._project_root) / "anti_ai_rules.json")
        if self._data_root is not None:
            root = StoragePaths(self._data_root)
            paths.append(root.assets / "anti_ai_rules.json")
            paths.append(root.root / "anti_ai_rules.json")
        paths.append(self._packaged_path)
        return paths

    def resolve_path(self) -> Path:
        for path in self.candidates():
            if path.is_file():
                return path
        return self._packaged_path

    def load(self) -> AntiAiRules:
        path = self.resolve_path()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid anti_ai_rules.json (expected object): {path}")
        forbidden_raw = raw.get("forbidden") or []
        forbidden = tuple(str(item).strip() for item in forbidden_raw if str(item).strip())
        negative = str(raw.get("negative_prompt") or "").strip()
        if not negative and forbidden:
            negative = ", ".join(forbidden)
        return AntiAiRules(forbidden=forbidden, negative_prompt=negative)
