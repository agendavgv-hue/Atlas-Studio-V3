"""Sidecar metadata written beside every generated image."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ImageArtifactMetadata:
    prompt: str
    negative_prompt: str
    seed: int
    steps: int
    cfg_scale: float
    sampler: str
    model: str
    width: int
    height: int
    generation_time_ms: float
    index: int
    provider: str = "forge"

    def write_beside(self, image_path: Path) -> Path:
        meta_path = image_path.with_suffix(".json")
        meta_path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        return meta_path
