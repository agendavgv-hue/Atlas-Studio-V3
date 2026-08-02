"""Map Style DNA into concrete composer layout parameters."""

from __future__ import annotations

from dataclasses import dataclass

from app.thumbnail.style_dna.models import ThumbnailStyleDNA


@dataclass(frozen=True)
class TextLayoutSpec:
    align_left: bool
    max_width_ratio: float
    top_ratio: float
    max_lines: int
    headline_scale: float
    line_break_mode: str
    outline: bool
    shadow: bool
    margin_x_ratio: float
    use_soft_vignette: bool


def text_layout_from_dna(dna: ThumbnailStyleDNA | None) -> TextLayoutSpec | None:
    if dna is None:
        return None
    align_left = dna.text_alignment != "right" and dna.text_position != "right"
    return TextLayoutSpec(
        align_left=align_left,
        max_width_ratio=max(0.28, min(0.62, float(dna.text_width or 0.39))),
        top_ratio=max(0.06, min(0.28, float(dna.text_top or 0.14))),
        max_lines=max(1, min(6, int(dna.text_max_lines or 3))),
        headline_scale=max(1.0, min(2.6, float(dna.headline_scale or 1.0))),
        line_break_mode=str(dna.line_break_mode or "wrapped_phrase"),
        outline=bool(dna.outline),
        shadow=bool(dna.shadow),
        margin_x_ratio=max(0.03, min(0.10, float(dna.margin_x or 0.05))),
        use_soft_vignette=align_left,
    )


def split_hook_lines(
    hook: str,
    *,
    max_words: int,
    max_lines: int,
    line_break_mode: str,
) -> list[str]:
    """Learn channel title stacking — e.g. THE / MARY / CELESTE vs one phrase."""
    words = [w for w in (hook or "").strip().upper().split() if w]
    if max_words > 0:
        words = words[:max_words]
    if not words:
        return []
    mode = (line_break_mode or "").casefold()
    if mode == "stacked_words" and len(words) <= max_lines:
        return words
    if mode == "stacked_words" and len(words) > max_lines:
        # Keep first lines as single words; fold the rest into the last line.
        head = words[: max_lines - 1]
        tail = " ".join(words[max_lines - 1 :])
        return [*head, tail]
    # wrapped_phrase: leave as one string for font-metric wrapping
    return [" ".join(words)]
