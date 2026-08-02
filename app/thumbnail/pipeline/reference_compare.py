"""Reference comparison — visual similarity vs Channel Studio thumbnail refs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtGui import QColor, QImage

from app.creative.engine.style_profile import StyleProfile


@dataclass
class ReferenceSimilarityReport:
    reference_count: int = 0
    similarity_score: float = 0.0
    composition: float = 0.0
    color: float = 0.0
    contrast: float = 0.0
    lighting: float = 0.0
    subject: float = 0.0
    negative_space: float = 0.0
    atmosphere: float = 0.0
    documentary: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_to_references(
    image_png: bytes,
    *,
    reference_paths: list[Path],
    thumbnail_profile: StyleProfile | None = None,
) -> ReferenceSimilarityReport:
    """Heuristic similarity (offline). Higher = closer to trained channel look."""
    refs = [Path(p) for p in reference_paths if Path(p).is_file()]
    if not image_png:
        return ReferenceSimilarityReport(notes=["empty image"])

    generated = QImage.fromData(image_png)
    if generated.isNull():
        return ReferenceSimilarityReport(
            reference_count=len(refs), notes=["could not decode generated image"]
        )

    gen_stats = _image_stats(generated)
    if not refs and thumbnail_profile is None:
        # No training data — neutral baseline (empty channel).
        return ReferenceSimilarityReport(
            reference_count=0,
            similarity_score=55.0,
            composition=55.0,
            color=55.0,
            contrast=55.0,
            lighting=55.0,
            subject=55.0,
            negative_space=55.0,
            atmosphere=55.0,
            documentary=55.0,
            notes=["No thumbnail references — neutral similarity baseline."],
        )

    ref_stats = [_image_stats(QImage(str(p))) for p in refs[:12]]
    ref_stats = [s for s in ref_stats if s is not None]
    target = _average_stats(ref_stats) if ref_stats else None

    # Blend profile hints when refs sparse.
    color_score = 70.0
    contrast_score = 70.0
    lighting_score = 70.0
    composition_score = 70.0
    subject_score = 70.0
    neg_score = 70.0
    atmosphere_score = 70.0
    documentary_score = 75.0
    notes: list[str] = []

    if target is not None and gen_stats is not None:
        color_score = _palette_similarity(gen_stats["colors"], target["colors"])
        contrast_score = _proximity(gen_stats["contrast"], target["contrast"], span=120)
        lighting_score = _proximity(gen_stats["brightness"], target["brightness"], span=100)
        composition_score = _proximity(
            gen_stats["right_weight"], target["right_weight"], span=0.45
        )
        subject_score = composition_score
        neg_score = _proximity(
            gen_stats["left_dark_ratio"], target["left_dark_ratio"], span=0.4
        )
        atmosphere_score = (lighting_score + contrast_score) / 2.0
        documentary_score = min(100.0, (contrast_score + lighting_score + color_score) / 3.0 + 5)
        notes.append(f"Compared against {len(ref_stats)} reference file(s).")
    elif thumbnail_profile is not None and gen_stats is not None:
        notes.append("Compared against style profile (no readable ref pixels).")
        if thumbnail_profile.dominant_colors:
            color_score = _palette_similarity(
                gen_stats["colors"], thumbnail_profile.dominant_colors
            )
        want_dark = thumbnail_profile.brightness == "dark"
        is_dark = gen_stats["brightness"] < 95
        lighting_score = 90.0 if want_dark == is_dark else 60.0
        want_high = "high" in (thumbnail_profile.contrast or "")
        is_high = gen_stats["contrast"] > 110
        contrast_score = 90.0 if want_high == is_high else 65.0
        if thumbnail_profile.subject_bias == "right":
            subject_score = 88.0 if gen_stats["right_weight"] >= 0.48 else 62.0
        else:
            subject_score = 88.0 if gen_stats["right_weight"] < 0.52 else 62.0
        composition_score = subject_score
        neg_score = 85.0 if thumbnail_profile.negative_space else 70.0
        atmosphere_score = (lighting_score + contrast_score) / 2.0
        documentary_score = min(
            100.0, float(thumbnail_profile.realism) * 0.9 + contrast_score * 0.1
        )

    scores = [
        composition_score,
        color_score,
        contrast_score,
        lighting_score,
        subject_score,
        neg_score,
        atmosphere_score,
        documentary_score,
    ]
    overall = round(sum(scores) / len(scores), 2)
    return ReferenceSimilarityReport(
        reference_count=len(refs),
        similarity_score=overall,
        composition=round(composition_score, 2),
        color=round(color_score, 2),
        contrast=round(contrast_score, 2),
        lighting=round(lighting_score, 2),
        subject=round(subject_score, 2),
        negative_space=round(neg_score, 2),
        atmosphere=round(atmosphere_score, 2),
        documentary=round(documentary_score, 2),
        notes=notes,
    )


def _image_stats(image: QImage) -> dict[str, Any] | None:
    if image.isNull():
        return None
    sample = image.scaled(64, 36)
    colors: list[str] = []
    lumas: list[float] = []
    right_luma = 0.0
    left_luma = 0.0
    left_n = 0
    right_n = 0
    left_dark = 0
    w, h = sample.width(), sample.height()
    for y in range(h):
        for x in range(w):
            c = QColor(sample.pixel(x, y))
            qr = (c.red() // 32) * 32
            qg = (c.green() // 32) * 32
            qb = (c.blue() // 32) * 32
            colors.append(f"#{qr:02x}{qg:02x}{qb:02x}")
            luma = 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()
            lumas.append(luma)
            if x < w // 3:
                left_luma += luma
                left_n += 1
                if luma < 90:
                    left_dark += 1
            if x > (2 * w) // 3:
                right_luma += luma
                right_n += 1
    if not lumas:
        return None
    avg = sum(lumas) / len(lumas)
    contrast = max(lumas) - min(lumas)
    # Brighter side often holds subject highlights; use inverse dark weight.
    right_avg = (right_luma / right_n) if right_n else avg
    left_avg = (left_luma / left_n) if left_n else avg
    right_weight = right_avg / (right_avg + left_avg + 1e-6)
    return {
        "colors": colors,
        "brightness": avg,
        "contrast": contrast,
        "right_weight": right_weight,
        "left_dark_ratio": (left_dark / left_n) if left_n else 0.0,
    }


def _average_stats(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    colors: list[str] = []
    for item in items:
        colors.extend(item["colors"][:200])
    return {
        "colors": colors,
        "brightness": sum(i["brightness"] for i in items) / len(items),
        "contrast": sum(i["contrast"] for i in items) / len(items),
        "right_weight": sum(i["right_weight"] for i in items) / len(items),
        "left_dark_ratio": sum(i["left_dark_ratio"] for i in items) / len(items),
    }


def _proximity(value: float, target: float, *, span: float) -> float:
    if span <= 0:
        return 100.0
    delta = abs(float(value) - float(target))
    return max(0.0, min(100.0, 100.0 - (delta / span) * 100.0))


def _palette_similarity(colors_a: list[str], colors_b: list[str]) -> float:
    if not colors_a or not colors_b:
        return 60.0
    set_a = set(colors_a[:40])
    set_b = set(colors_b[:40])
    if not set_a or not set_b:
        return 60.0
    overlap = len(set_a & set_b) / max(1, min(len(set_a), len(set_b)))
    # Soft match on quantized buckets
    return max(45.0, min(100.0, 50.0 + overlap * 50.0))
