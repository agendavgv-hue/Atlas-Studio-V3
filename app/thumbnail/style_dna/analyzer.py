"""ThumbnailStyleAnalyzer — learn complete thumbnail Style DNA from all references."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.thumbnail.style_dna.aggregator import aggregate_style_dna
from app.thumbnail.style_dna.geometry import analyze_reference_geometry
from app.thumbnail.style_dna.models import ReferenceStyleSample, ThumbnailStyleDNA


class ThumbnailStyleAnalyzer:
    """Analyze ALL reference thumbnails (text, logo, frame geometry, composition)."""

    def analyze(
        self,
        references: list[Path],
        *,
        studio_hints: dict[str, Any] | None = None,
    ) -> ThumbnailStyleDNA:
        samples: list[ReferenceStyleSample] = []
        for path in references:
            p = Path(path)
            if not p.is_file():
                continue
            sample = analyze_reference_geometry(p)
            if sample is not None:
                samples.append(sample)
        return aggregate_style_dna(samples, studio_hints=studio_hints)
