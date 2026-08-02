"""Thumbnail Style DNA — learned complete thumbnail layout (not guesswork)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ReferenceStyleSample:
    """Per-reference geometry sample before averaging."""

    path: str = ""
    text_position: str = "left"
    text_alignment: str = "left"
    text_top: float = 0.12
    text_height: float = 0.40
    text_width: float = 0.38
    text_lines: int = 3
    text_coverage: float = 0.40
    headline_scale: float = 1.0
    outline_likely: bool = True
    shadow_likely: bool = True
    logo_position: str = "bottom_left"
    logo_scale: float = 0.10
    logo_margin: float = 0.04
    subject_position: str = "right"
    negative_space: str = "left"
    focus_x: float = 0.68
    focus_y: float = 0.45
    rule_of_thirds: bool = True
    visual_balance: float = 0.55
    dominant_colors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ReferenceStyleSample:
        raw = dict(data or {})
        return cls(
            path=str(raw.get("path") or ""),
            text_position=str(raw.get("text_position") or "left"),
            text_alignment=str(raw.get("text_alignment") or "left"),
            text_top=float(raw.get("text_top") or 0.12),
            text_height=float(raw.get("text_height") or 0.40),
            text_width=float(raw.get("text_width") or 0.38),
            text_lines=max(1, int(raw.get("text_lines") or 3)),
            text_coverage=float(raw.get("text_coverage") or 0.40),
            headline_scale=float(raw.get("headline_scale") or 1.0),
            outline_likely=bool(raw.get("outline_likely", True)),
            shadow_likely=bool(raw.get("shadow_likely", True)),
            logo_position=str(raw.get("logo_position") or "bottom_left"),
            logo_scale=float(raw.get("logo_scale") or 0.10),
            logo_margin=float(raw.get("logo_margin") or 0.04),
            subject_position=str(raw.get("subject_position") or "right"),
            negative_space=str(raw.get("negative_space") or "left"),
            focus_x=float(raw.get("focus_x") or 0.68),
            focus_y=float(raw.get("focus_y") or 0.45),
            rule_of_thirds=bool(raw.get("rule_of_thirds", True)),
            visual_balance=float(raw.get("visual_balance") or 0.55),
            dominant_colors=[str(c) for c in (raw.get("dominant_colors") or [])][:6],
            notes=[str(n) for n in (raw.get("notes") or [])],
        )


@dataclass
class ThumbnailStyleDNA:
    """Complete averaged Style DNA for one channel's thumbnails."""

    # User-facing schema (thumbnail_style_profile.json)
    text_position: str = "left"
    text_alignment: str = "left"
    text_max_lines: int = 3
    text_coverage: float = 0.42
    text_top: float = 0.14
    text_height: float = 0.44
    text_width: float = 0.39
    headline_scale: float = 1.8
    dominant_word: str = "largest"
    line_break_mode: str = "stacked_words"  # stacked_words | wrapped_phrase
    outline: bool = True
    shadow: bool = True
    logo_position: str = "bottom_left"
    logo_scale: float = 0.11
    logo_margin: float = 0.04
    subject_position: str = "right"
    negative_space: str = "left"
    rule_of_thirds: bool = True
    composition: str = "cinematic"
    brand_style: str = "premium_documentary"
    margin_x: float = 0.05
    margin_y: float = 0.08
    focus_x: float = 0.68
    focus_y: float = 0.45
    visual_balance: float = 0.55
    # Legacy StyleProfile-compatible fields
    kind: str = "thumbnails"
    reference_count: int = 0
    dominant_colors: list[str] = field(default_factory=list)
    contrast: str = "high"
    brightness: str = "dark"
    color_temperature: str = "warm"
    subject_bias: str = "right"
    camera_angle: str = "eye_level"
    atmosphere: str = "cinematic"
    realism: float = 85.0
    mood: str = "mystery"
    logo_bias: str = "bottom_left"
    average_words: int = 4
    notes: list[str] = field(default_factory=list)
    samples: list[ReferenceStyleSample] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            # Sprint schema
            "text_position": self.text_position,
            "text_alignment": self.text_alignment,
            "text_max_lines": self.text_max_lines,
            "text_coverage": round(self.text_coverage, 4),
            "text_top": round(self.text_top, 4),
            "text_height": round(self.text_height, 4),
            "text_width": round(self.text_width, 4),
            "headline_scale": round(self.headline_scale, 3),
            "dominant_word": self.dominant_word,
            "line_break_mode": self.line_break_mode,
            "outline": self.outline,
            "shadow": self.shadow,
            "logo_position": self.logo_position,
            "logo_scale": round(self.logo_scale, 4),
            "logo_margin": round(self.logo_margin, 4),
            "subject_position": self.subject_position,
            "negative_space": self.negative_space,
            "rule_of_thirds": self.rule_of_thirds,
            "composition": self.composition,
            "brand_style": self.brand_style,
            "margin_x": round(self.margin_x, 4),
            "margin_y": round(self.margin_y, 4),
            "focus_x": round(self.focus_x, 4),
            "focus_y": round(self.focus_y, 4),
            "visual_balance": round(self.visual_balance, 4),
            # Legacy / StyleProfile
            "kind": self.kind,
            "reference_count": self.reference_count,
            "dominant_colors": list(self.dominant_colors),
            "contrast": self.contrast,
            "brightness": self.brightness,
            "color_temperature": self.color_temperature,
            "subject_bias": self.subject_bias,
            "camera_angle": self.camera_angle,
            "atmosphere": self.atmosphere,
            "realism": self.realism,
            "mood": self.mood,
            "logo_bias": self.logo_bias,
            "average_words": self.average_words,
            "notes": list(self.notes),
            "samples": [s.to_dict() for s in self.samples],
            "extras": dict(self.extras),
            # Debug-facing labels
            "Text Layout": f"{self.text_max_lines} lines",
            "Headline Scale": round(self.headline_scale, 2),
            "Logo": self.logo_position.replace("_", " ").title(),
            "Negative Space": self.negative_space.title(),
            "Subject": self.subject_position.title(),
        }
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ThumbnailStyleDNA:
        raw = dict(data or {})
        samples = [
            ReferenceStyleSample.from_dict(item)
            for item in (raw.get("samples") or [])
            if isinstance(item, dict)
        ]
        return cls(
            text_position=str(raw.get("text_position") or "left"),
            text_alignment=str(raw.get("text_alignment") or "left"),
            text_max_lines=max(1, int(raw.get("text_max_lines") or 3)),
            text_coverage=float(raw.get("text_coverage") or 0.42),
            text_top=float(raw.get("text_top") or 0.14),
            text_height=float(raw.get("text_height") or 0.44),
            text_width=float(raw.get("text_width") or 0.39),
            headline_scale=float(raw.get("headline_scale") or 1.8),
            dominant_word=str(raw.get("dominant_word") or "largest"),
            line_break_mode=str(raw.get("line_break_mode") or "stacked_words"),
            outline=bool(raw.get("outline", True)),
            shadow=bool(raw.get("shadow", True)),
            logo_position=str(
                raw.get("logo_position") or raw.get("logo_bias") or "bottom_left"
            ),
            logo_scale=float(raw.get("logo_scale") or 0.11),
            logo_margin=float(raw.get("logo_margin") or 0.04),
            subject_position=str(
                raw.get("subject_position") or raw.get("subject_bias") or "right"
            ),
            negative_space=str(raw.get("negative_space") or "left"),
            rule_of_thirds=bool(raw.get("rule_of_thirds", True)),
            composition=str(raw.get("composition") or "cinematic"),
            brand_style=str(raw.get("brand_style") or "premium_documentary"),
            margin_x=float(raw.get("margin_x") or 0.05),
            margin_y=float(raw.get("margin_y") or 0.08),
            focus_x=float(raw.get("focus_x") or 0.68),
            focus_y=float(raw.get("focus_y") or 0.45),
            visual_balance=float(raw.get("visual_balance") or 0.55),
            kind=str(raw.get("kind") or "thumbnails"),
            reference_count=int(raw.get("reference_count") or 0),
            dominant_colors=[str(c) for c in (raw.get("dominant_colors") or [])][:6],
            contrast=str(raw.get("contrast") or "high"),
            brightness=str(raw.get("brightness") or "dark"),
            color_temperature=str(raw.get("color_temperature") or "warm"),
            subject_bias=str(
                raw.get("subject_bias") or raw.get("subject_position") or "right"
            ),
            camera_angle=str(raw.get("camera_angle") or "eye_level"),
            atmosphere=str(raw.get("atmosphere") or "cinematic"),
            realism=float(raw.get("realism") or 85.0),
            mood=str(raw.get("mood") or "mystery"),
            logo_bias=str(raw.get("logo_bias") or raw.get("logo_position") or "bottom_left"),
            average_words=int(raw.get("average_words") or raw.get("text_max_lines") or 4),
            notes=[str(n) for n in (raw.get("notes") or [])],
            samples=samples,
            extras=dict(raw.get("extras") or {}),
        )

    def prompt_block(self) -> str:
        colors = ", ".join(self.dominant_colors[:4]) or "channel brand colors"
        return (
            "REFERENCE STYLE DNA — match uploaded thumbnails as primary visual style:\n"
            f"- Text: {self.text_position}/{self.text_alignment}, "
            f"{self.text_max_lines} lines, coverage {self.text_coverage:.0%}, "
            f"top {self.text_top:.0%}, width {self.text_width:.0%}, "
            f"headline scale {self.headline_scale:.2f}×, break={self.line_break_mode}\n"
            f"- Outline={self.outline}; Shadow={self.shadow}\n"
            f"- Logo: {self.logo_position} @ {self.logo_scale:.0%} "
            f"(margin {self.logo_margin:.0%})\n"
            f"- Subject: {self.subject_position}; negative space: {self.negative_space}\n"
            f"- Composition: {self.composition}; brand_style: {self.brand_style}; "
            f"rule_of_thirds={self.rule_of_thirds}\n"
            f"- Colors: {colors}; contrast {self.contrast}; brightness {self.brightness}\n"
            f"- Built from {self.reference_count} complete thumbnail reference(s).\n"
            "Reproduce the same text hierarchy, margins, logo placement, and composition."
        )

    def debug_rows(self) -> list[tuple[str, str]]:
        return [
            ("Text Layout", f"{self.text_max_lines} regels"),
            ("Headline Scale", f"{self.headline_scale:.2f}"),
            ("Text Coverage", f"{self.text_coverage:.0%}"),
            ("Line Break", self.line_break_mode.replace("_", " ")),
            ("Logo", self.logo_position.replace("_", " ").title()),
            ("Logo Scale", f"{self.logo_scale:.0%}"),
            ("Negative Space", self.negative_space.title()),
            ("Subject", self.subject_position.title()),
            ("Outline / Shadow", f"{'Ja' if self.outline else 'Nee'} / {'Ja' if self.shadow else 'Nee'}"),
            ("Composition", self.composition),
            ("Brand Style", self.brand_style.replace("_", " ")),
            ("References", str(self.reference_count)),
        ]
