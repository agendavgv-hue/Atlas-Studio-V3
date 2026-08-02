"""Typography Engine — score line-break candidates from Style DNA."""

from __future__ import annotations

from dataclasses import dataclass

from app.thumbnail.style_dna.models import ThumbnailStyleDNA


@dataclass(frozen=True)
class LineBreakCandidate:
    lines: list[str]
    score: float
    why: str = ""


def invent_line_breaks(
    hook: str,
    *,
    style_dna: ThumbnailStyleDNA | None = None,
    max_words: int = 4,
) -> list[LineBreakCandidate]:
    """Enumerate break patterns and score them (THE/MARY/CELESTE wins when DNA agrees)."""
    words = [w for w in (hook or "").strip().upper().split() if w]
    if max_words > 0:
        words = words[:max_words]
    if not words:
        return [LineBreakCandidate(lines=[], score=0.0, why="empty hook")]

    preferred_lines = int(style_dna.text_max_lines) if style_dna else 3
    prefer_stacked = bool(
        style_dna and style_dna.line_break_mode == "stacked_words"
    )
    prefer_scale = float(style_dna.headline_scale) if style_dna else 1.5

    patterns: list[list[str]] = []
    # One word per line
    if len(words) <= 4:
        patterns.append(list(words))
    # All one line
    patterns.append([" ".join(words)])
    # Balanced 2-line splits
    if len(words) >= 2:
        for i in range(1, len(words)):
            patterns.append([" ".join(words[:i]), " ".join(words[i:])])
    # 3-line folds
    if len(words) >= 3:
        for i in range(1, len(words) - 1):
            for j in range(i + 1, len(words)):
                patterns.append(
                    [
                        " ".join(words[:i]),
                        " ".join(words[i:j]),
                        " ".join(words[j:]),
                    ]
                )
    # Prefer DNA max lines: pad/truncate variants already covered

    scored: list[LineBreakCandidate] = []
    seen: set[tuple[str, ...]] = set()
    for lines in patterns:
        key = tuple(lines)
        if key in seen or not all(lines):
            continue
        seen.add(key)
        score, why = _score_break(
            lines,
            word_count=len(words),
            preferred_lines=preferred_lines,
            prefer_stacked=prefer_stacked,
            prefer_scale=prefer_scale,
        )
        scored.append(LineBreakCandidate(lines=lines, score=score, why=why))

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored


def best_line_break(
    hook: str,
    *,
    style_dna: ThumbnailStyleDNA | None = None,
    max_words: int = 4,
) -> LineBreakCandidate:
    candidates = invent_line_breaks(hook, style_dna=style_dna, max_words=max_words)
    return candidates[0] if candidates else LineBreakCandidate(lines=[], score=0.0)


def _score_break(
    lines: list[str],
    *,
    word_count: int,
    preferred_lines: int,
    prefer_stacked: bool,
    prefer_scale: float,
) -> tuple[float, str]:
    score = 55.0
    n = len(lines)
    # Prefer DNA line count
    score += max(0.0, 25.0 - abs(n - preferred_lines) * 10.0)
    stacked = all(len(line.split()) == 1 for line in lines)
    if prefer_stacked and stacked and n == word_count:
        score += 30.0
        why = "stacked single words match Style DNA"
    elif prefer_stacked and stacked:
        score += 18.0
        why = "stacked words, close to DNA"
    elif stacked and n >= 2:
        score += 8.0
        why = "stacked words"
    elif n == 1:
        score -= 8.0
        why = "single line — weaker hierarchy"
    else:
        why = "phrase wrap"

    # Dominant middle word bonus when 3 lines
    if n == 3 and prefer_scale >= 1.3:
        mid = lines[1]
        if len(mid.split()) == 1 and len(mid) >= max(len(lines[0]), len(lines[2])):
            score += 10.0
            why += "; dominant middle word"

    # Penalize uneven long first line with tiny second
    if n == 2 and len(lines[0]) > len(lines[1]) * 2.5:
        score -= 12.0
        why += "; uneven split"

    return round(max(0.0, min(100.0, score)), 2), why
