"""Aggregate per-reference samples into Style DNA averages."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.thumbnail.style_dna.models import ReferenceStyleSample, ThumbnailStyleDNA


def aggregate_style_dna(
    samples: list[ReferenceStyleSample],
    *,
    studio_hints: dict[str, Any] | None = None,
) -> ThumbnailStyleDNA:
    hints = dict(studio_hints or {})
    if not samples:
        return ThumbnailStyleDNA(
            reference_count=0,
            mood=str(hints.get("emotion") or hints.get("mood") or "mystery"),
            contrast=str(hints.get("contrast") or "high"),
            average_words=int(hints.get("max_words") or 4),
            text_max_lines=min(4, int(hints.get("max_words") or 3)),
            notes=["No reference thumbnails — using Channel Studio settings only."],
        )

    def mode(values: list[str], default: str) -> str:
        if not values:
            return default
        return Counter(values).most_common(1)[0][0]

    def avg(values: list[float], default: float) -> float:
        return sum(values) / len(values) if values else default

    text_pos = mode([s.text_position for s in samples], "left")
    text_align = mode([s.text_alignment for s in samples], text_pos)
    subject = mode([s.subject_position for s in samples], "right")
    neg = mode([s.negative_space for s in samples], "left")
    logo = mode([s.logo_position for s in samples], "bottom_left")

    avg_lines = avg([float(s.text_lines) for s in samples], 3.0)
    text_max_lines = max(1, min(6, int(round(avg_lines))))
    headline = avg([s.headline_scale for s in samples], 1.5)
    # Prefer stacked words when majority of samples look stacked and lines ≥ 2
    stacked_votes = sum(
        1 for s in samples if "stacked_word_lines_detected" in s.notes
    )
    line_break = (
        "stacked_words"
        if stacked_votes >= max(1, len(samples) // 2) and text_max_lines >= 2
        else "wrapped_phrase"
    )

    colors: list[str] = []
    for s in samples:
        colors.extend(s.dominant_colors)
    dominant = [c for c, _ in Counter(colors).most_common(5)]

    # Lighting heuristics from colors
    brightness_vals = []
    for hex_c in dominant[:3]:
        try:
            r = int(hex_c[1:3], 16)
            g = int(hex_c[3:5], 16)
            b = int(hex_c[5:7], 16)
            brightness_vals.append(0.2126 * r + 0.7152 * g + 0.0722 * b)
        except (ValueError, IndexError):
            pass
    avg_b = avg(brightness_vals, 70.0)
    brightness = "dark" if avg_b < 85 else "medium" if avg_b < 140 else "bright"
    warm = sum(
        1
        for hex_c in dominant[:3]
        if len(hex_c) >= 7 and int(hex_c[1:3], 16) >= int(hex_c[5:7], 16)
    )
    temperature = "warm" if warm >= 1 else "cool"

    logo_hint = str(hints.get("logo_position") or "").strip().casefold()
    if logo_hint not in {"", "auto"}:
        logo = logo_hint
    neg_hint = str(hints.get("negative_space") or "").strip().casefold()
    if neg_hint not in {"", "auto"}:
        neg = neg_hint
        text_pos = neg if neg in {"left", "right"} else text_pos
    subject_hint = str(hints.get("subject_bias") or "").strip().casefold()
    if subject_hint not in {"", "auto"}:
        subject = subject_hint

    composition = str(hints.get("composition") or "cinematic")
    if composition in {"close_up", "medium", "wide"}:
        composition = "cinematic"
    brand_style = str(hints.get("brand_style") or "premium_documentary")
    mood = str(hints.get("emotion") or hints.get("mood") or "mystery")
    max_words = int(hints.get("max_words") or max(text_max_lines, 3))

    dna = ThumbnailStyleDNA(
        text_position=text_pos,
        text_alignment=text_align,
        text_max_lines=text_max_lines,
        text_coverage=avg([s.text_coverage for s in samples], 0.42),
        text_top=avg([s.text_top for s in samples], 0.14),
        text_height=avg([s.text_height for s in samples], 0.44),
        text_width=avg([s.text_width for s in samples], 0.39),
        headline_scale=max(1.0, min(2.6, headline)),
        dominant_word="largest" if headline >= 1.25 else "equal",
        line_break_mode=line_break,
        outline=sum(1 for s in samples if s.outline_likely) >= len(samples) / 2,
        shadow=sum(1 for s in samples if s.shadow_likely) >= len(samples) / 2,
        logo_position=logo,
        logo_scale=avg([s.logo_scale for s in samples], 0.11),
        logo_margin=avg([s.logo_margin for s in samples], 0.04),
        subject_position=subject,
        negative_space=neg,
        rule_of_thirds=sum(1 for s in samples if s.rule_of_thirds) >= len(samples) / 2,
        composition=composition,
        brand_style=brand_style,
        margin_x=max(0.03, avg([s.logo_margin for s in samples], 0.05)),
        margin_y=max(0.05, avg([s.text_top for s in samples], 0.08) * 0.7),
        focus_x=avg([s.focus_x for s in samples], 0.68),
        focus_y=avg([s.focus_y for s in samples], 0.45),
        visual_balance=avg([s.visual_balance for s in samples], 0.55),
        kind="thumbnails",
        reference_count=len(samples),
        dominant_colors=dominant,
        contrast=str(hints.get("contrast") or "very_high"),
        brightness=brightness,
        color_temperature=temperature,
        subject_bias=subject,
        atmosphere=str(hints.get("atmosphere") or "cinematic"),
        realism=float(hints.get("realism") or 85.0),
        mood=mood,
        logo_bias=logo,
        average_words=max_words,
        notes=[
            f"Analyzed {len(samples)} complete thumbnail reference(s).",
            f"Text {text_pos} · {text_max_lines} lines · coverage "
            f"{avg([s.text_coverage for s in samples], 0.42):.0%}.",
            f"Logo {logo} @ {avg([s.logo_scale for s in samples], 0.11):.0%}.",
            f"Subject {subject}; negative space {neg}; break={line_break}.",
        ],
        samples=list(samples),
        extras={
            "text_left_pct": 100.0 if text_pos == "left" else 0.0,
            "text_top_pct": round(avg([s.text_top for s in samples], 0.14) * 100, 1),
            "avg_lines": round(avg_lines, 2),
            "avg_text_height_pct": round(
                avg([s.text_height for s in samples], 0.44) * 100, 1
            ),
            "avg_text_width_pct": round(
                avg([s.text_width for s in samples], 0.39) * 100, 1
            ),
            "stacked_votes": stacked_votes,
        },
    )
    return dna
