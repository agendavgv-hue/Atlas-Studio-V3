"""Reference style profiles derived from Channel Studio uploads."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtGui import QColor, QImage


@dataclass
class StyleProfile:
    """Averaged visual style from reference images (generic, not channel-hardcoded)."""

    kind: str  # thumbnails | images
    reference_count: int = 0
    dominant_colors: list[str] = field(default_factory=list)
    contrast: str = "high"
    brightness: str = "dark"
    color_temperature: str = "warm"
    subject_bias: str = "right"
    negative_space: str = "left"
    camera_angle: str = "eye_level"
    atmosphere: str = "cinematic"
    realism: float = 85.0
    mood: str = "mystery"
    logo_bias: str = "bottom_left"
    average_words: int = 4
    text_position: str = "left"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, kind: str = "thumbnails") -> StyleProfile:
        raw = dict(data or {})
        return cls(
            kind=str(raw.get("kind") or kind),
            reference_count=int(raw.get("reference_count") or 0),
            dominant_colors=[str(c) for c in (raw.get("dominant_colors") or [])][:6],
            contrast=str(raw.get("contrast") or "high"),
            brightness=str(raw.get("brightness") or "dark"),
            color_temperature=str(raw.get("color_temperature") or "warm"),
            subject_bias=str(raw.get("subject_bias") or "right"),
            negative_space=str(raw.get("negative_space") or "left"),
            camera_angle=str(raw.get("camera_angle") or "eye_level"),
            atmosphere=str(raw.get("atmosphere") or "cinematic"),
            realism=float(raw.get("realism") or 85.0),
            mood=str(raw.get("mood") or "mystery"),
            logo_bias=str(raw.get("logo_bias") or "bottom_left"),
            average_words=int(raw.get("average_words") or 4),
            text_position=str(raw.get("text_position") or "left"),
            notes=[str(n) for n in (raw.get("notes") or [])],
        )

    def prompt_block(self) -> str:
        colors = ", ".join(self.dominant_colors[:4]) or "channel brand colors"
        return (
            "REFERENCE STYLE PROFILE — match uploaded references as primary visual style:\n"
            f"- Dominant colors: {colors}\n"
            f"- Contrast: {self.contrast}; brightness: {self.brightness}; "
            f"temperature: {self.color_temperature}\n"
            f"- Subject bias: {self.subject_bias}; negative space: {self.negative_space}\n"
            f"- Camera: {self.camera_angle}; atmosphere: {self.atmosphere}; "
            f"mood: {self.mood}; realism {self.realism:.0f}\n"
            f"- Typography space: {self.text_position}; ~{self.average_words} words\n"
            f"- Logo bias: {self.logo_bias}\n"
            f"- Built from {self.reference_count} reference file(s).\n"
            "Use the uploaded reference thumbnails/images as the primary visual style. "
            "Maintain the same cinematic composition, lighting, typography spacing, "
            "and premium documentary atmosphere. Follow the same visual identity."
        )


def analyze_reference_images(
    paths: list[Path],
    *,
    kind: str,
    studio_hints: dict[str, Any] | None = None,
) -> StyleProfile:
    """Heuristic style analysis (no AI). Works offline for any channel."""
    hints = dict(studio_hints or {})
    usable = [Path(p) for p in paths if Path(p).is_file()]
    if not usable:
        return StyleProfile(
            kind=kind,
            reference_count=0,
            contrast=str(hints.get("contrast") or "high"),
            negative_space=str(hints.get("negative_space") or "left"),
            mood=str(hints.get("emotion") or hints.get("mood") or "mystery"),
            notes=["No reference files — using Channel Studio settings only."],
        )

    colors: list[str] = []
    brightness_vals: list[float] = []
    contrast_vals: list[float] = []
    left_dark = 0
    right_dark = 0

    for path in usable[:20]:
        image = QImage(str(path))
        if image.isNull():
            continue
        sample = image.scaled(64, 36)
        bucket: Counter[str] = Counter()
        lumas: list[float] = []
        w, h = sample.width(), sample.height()
        for y in range(h):
            for x in range(w):
                c = QColor(sample.pixel(x, y))
                # Quantize to reduce noise.
                qr = (c.red() // 32) * 32
                qg = (c.green() // 32) * 32
                qb = (c.blue() // 32) * 32
                bucket[f"#{qr:02x}{qg:02x}{qb:02x}"] += 1
                luma = 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()
                lumas.append(luma)
                if x < w // 3 and luma < 90:
                    left_dark += 1
                if x > (2 * w) // 3 and luma < 90:
                    right_dark += 1
        if bucket:
            colors.extend([hex_c for hex_c, _ in bucket.most_common(3)])
        if lumas:
            avg = sum(lumas) / len(lumas)
            brightness_vals.append(avg)
            contrast_vals.append(max(lumas) - min(lumas))

    # Aggregate
    color_counts = Counter(colors)
    dominant = [c for c, _ in color_counts.most_common(5)]
    avg_b = sum(brightness_vals) / len(brightness_vals) if brightness_vals else 90.0
    avg_c = sum(contrast_vals) / len(contrast_vals) if contrast_vals else 120.0

    brightness = "dark" if avg_b < 85 else "medium" if avg_b < 140 else "bright"
    contrast = "very_high" if avg_c > 160 else "high" if avg_c > 110 else "medium"
    # Darker side likely holds subject; opposite side is negative space for text.
    if right_dark >= left_dark:
        subject_bias = "right"
        negative_space = "left"
        text_position = "left"
        logo_bias = "bottom_left"
    else:
        subject_bias = "left"
        negative_space = "right"
        text_position = "right"
        logo_bias = "bottom_right"

    # Temperature from average of top colors
    warm = 0
    cool = 0
    for hex_c in dominant[:3]:
        r = int(hex_c[1:3], 16)
        b = int(hex_c[5:7], 16)
        if r >= b:
            warm += 1
        else:
            cool += 1
    temperature = "warm" if warm >= cool else "cool"

    # Prefer analyzed composition; only override logo when studio pin is explicit.
    logo_hint = str(hints.get("logo_position") or "").strip().casefold()
    if logo_hint in {"", "auto"}:
        logo_hint = logo_bias

    neg_hint = str(hints.get("negative_space") or "").strip().casefold()
    if neg_hint in {"", "auto"}:
        neg_hint = negative_space

    subject_hint = str(hints.get("subject_bias") or "").strip().casefold()
    if subject_hint in {"", "auto"}:
        subject_hint = subject_bias

    profile = StyleProfile(
        kind=kind,
        reference_count=len(usable),
        dominant_colors=dominant,
        contrast=str(hints.get("contrast") or contrast),
        brightness=brightness,
        color_temperature=temperature,
        subject_bias=subject_hint,
        negative_space=neg_hint,
        atmosphere=str(hints.get("atmosphere") or "cinematic"),
        realism=float(hints.get("realism") or 85.0),
        mood=str(hints.get("emotion") or hints.get("mood") or "mystery"),
        logo_bias=logo_hint,
        average_words=int(hints.get("max_words") or 4),
        text_position=str(hints.get("text_position") or text_position),
        notes=[
            f"Analyzed {len(usable)} reference file(s) heuristically.",
            f"Composition bias subject={subject_hint}, negative_space={neg_hint}.",
            f"Lighting read as {brightness}/{temperature}/{contrast}.",
        ],
    )
    return profile


def load_style_profile(path: Path, *, kind: str) -> StyleProfile | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return StyleProfile.from_dict(raw, kind=kind)


def save_style_profile(path: Path, profile: StyleProfile) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path
