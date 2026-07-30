"""Production Sheet parsing — single source of truth for all pipelines.

Canonical write format lives in ``app.pipelines.sheet_format``.
Every consumer (Images, Movie, Shorts, future SEO, …) must use these APIs.
Do not re-implement IMAGE / Duration / Prompt parsing elsewhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SheetImagePrompt:
    """One image prompt discovered in a production sheet (1-based index)."""

    index: int
    prompt: str


@dataclass(frozen=True)
class SheetBlock:
    """One IMAGE NN block with raw body lines (excluding the header)."""

    index: int
    body_lines: tuple[str, ...] = field(default_factory=tuple)


# Canonical header: IMAGE 01 / Image 01 (optional trailing : . -)
_IMAGE_HEADER = re.compile(
    r"^\s*(?:IMAGE|Image)\s*0*(\d+)\s*[:.\-]?\s*$",
    re.IGNORECASE,
)
_PROMPT_LABEL = re.compile(
    r"^\s*(?:Image\s+)?Prompt\s*:\s*(.*)$",
    re.IGNORECASE,
)
_IMAGE_PROMPT_INLINE = re.compile(
    r"^\s*Image\s+Prompt\s*:\s*(.*)$",
    re.IGNORECASE,
)
_DURATION_LINE = re.compile(
    r"(?im)^\s*duration\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*(s|sec|secs|seconds)?\s*$"
)
_LABEL_LINE = re.compile(
    r"(?im)^\s*(?:title|scene\s*title|label|name)\s*[:=]\s*(.+?)\s*$"
)
_META_LINE = re.compile(
    r"^\s*(Narration|Visual|Duration|Title|Label|Name|Scene\s*Title)\s*:",
    re.IGNORECASE,
)


def iter_image_blocks(sheet_text: str) -> list[SheetBlock]:
    """Split sheet text into ordered IMAGE NN blocks (canonical structure)."""
    lines = _normalize_lines(sheet_text)
    blocks: list[SheetBlock] = []
    i = 0
    while i < len(lines):
        header = _IMAGE_HEADER.match(lines[i])
        if not header:
            i += 1
            continue
        index = int(header.group(1))
        i += 1
        body: list[str] = []
        while i < len(lines) and not _IMAGE_HEADER.match(lines[i]):
            # Standalone Image Prompt: starts a legacy section — leave it outside.
            if _IMAGE_PROMPT_INLINE.match(lines[i]):
                break
            body.append(lines[i])
            i += 1
        blocks.append(SheetBlock(index=index, body_lines=tuple(body)))
    return blocks


def extract_image_prompt_entries(sheet_text: str) -> list[SheetImagePrompt]:
    """Image prompts with original IMAGE indexes (canonical blocks, then legacy)."""
    found: list[SheetImagePrompt] = []

    for block in iter_image_blocks(sheet_text):
        prompt = _prompt_from_block(block.body_lines)
        if prompt:
            found.append(SheetImagePrompt(index=block.index, prompt=prompt))

    next_index = (max((item.index for item in found), default=0) + 1)
    for item in _legacy_inline_prompts_outside_blocks(sheet_text):
        found.append(SheetImagePrompt(index=next_index, prompt=item.prompt))
        next_index += 1
    return found


def extract_image_prompts(sheet_text: str) -> list[SheetImagePrompt]:
    """Return ordered image prompts densely re-indexed from 1 for image_01..N."""
    found = extract_image_prompt_entries(sheet_text)
    if not found:
        return []
    return [
        SheetImagePrompt(index=position, prompt=item.prompt)
        for position, item in enumerate(found, start=1)
    ]


def extract_sheet_duration_map(sheet_text: str) -> dict[int, float]:
    """Map original IMAGE index → duration seconds."""
    by_index: dict[int, float] = {}
    for block in iter_image_blocks(sheet_text):
        duration = _duration_from_block(block.body_lines)
        if duration is not None:
            by_index[block.index] = duration
    return by_index


def extract_sheet_durations(sheet_text: str, image_count: int) -> list[float] | None:
    """Per-image durations for indexes ``1..image_count``, or None if incomplete.

    Uses canonical IMAGE blocks only (shared with prompt extraction).
    """
    if image_count < 1 or not (sheet_text or "").strip():
        return None

    by_index = extract_sheet_duration_map(sheet_text)
    if len(by_index) < image_count:
        return None
    durations = [by_index.get(i) for i in range(1, image_count + 1)]
    if any(value is None for value in durations):
        return None
    return [float(value) for value in durations]  # type: ignore[arg-type]


def extract_sheet_labels(sheet_text: str) -> dict[int, str]:
    """Optional Title/Label lines inside IMAGE blocks (keyed by IMAGE index)."""
    by_index: dict[int, str] = {}
    for block in iter_image_blocks(sheet_text):
        for line in block.body_lines:
            match = _LABEL_LINE.match(line)
            if match:
                by_index[block.index] = match.group(1).strip()
                break
    return by_index


def _duration_from_block(body_lines: tuple[str, ...]) -> float | None:
    for line in body_lines:
        match = _DURATION_LINE.match(line)
        if match:
            return max(0.5, float(match.group(1)))
    return None


def _prompt_from_block(body_lines: tuple[str, ...]) -> str:
    for idx, raw in enumerate(body_lines):
        label = _PROMPT_LABEL.match(raw) or _IMAGE_PROMPT_INLINE.match(raw)
        if not label:
            continue
        first = label.group(1).strip()
        if first:
            return first
        parts: list[str] = []
        for follow in body_lines[idx + 1 :]:
            if _PROMPT_LABEL.match(follow) or _IMAGE_PROMPT_INLINE.match(follow):
                break
            if not follow.strip():
                if parts:
                    break
                continue
            if _META_LINE.match(follow):
                if parts:
                    break
                continue
            parts.append(follow.strip())
        return " ".join(parts).strip()

    parts = []
    for raw in body_lines:
        if not raw.strip():
            if parts:
                break
            continue
        if _META_LINE.match(raw) or _DURATION_LINE.match(raw) or _LABEL_LINE.match(raw):
            continue
        parts.append(raw.strip())
    return " ".join(parts).strip()


def _legacy_inline_prompts_outside_blocks(sheet_text: str) -> list[SheetImagePrompt]:
    """Standalone ``Image Prompt:`` lines that are not inside IMAGE blocks."""
    lines = _normalize_lines(sheet_text)
    inside_block: set[int] = set()
    i = 0
    while i < len(lines):
        if _IMAGE_HEADER.match(lines[i]):
            i += 1
            while i < len(lines) and not _IMAGE_HEADER.match(lines[i]):
                if _IMAGE_PROMPT_INLINE.match(lines[i]):
                    break
                inside_block.add(i)
                i += 1
            continue
        i += 1

    found: list[SheetImagePrompt] = []
    auto_index = 1
    i = 0
    while i < len(lines):
        if i in inside_block:
            i += 1
            continue
        inline = _IMAGE_PROMPT_INLINE.match(lines[i])
        if not inline:
            i += 1
            continue
        rest = inline.group(1).strip()
        if rest:
            found.append(SheetImagePrompt(index=auto_index, prompt=rest))
            auto_index += 1
            i += 1
            continue
        parts: list[str] = []
        i += 1
        while i < len(lines):
            if i in inside_block or _IMAGE_HEADER.match(lines[i]) or _IMAGE_PROMPT_INLINE.match(lines[i]):
                break
            raw = lines[i]
            if not raw.strip():
                if parts:
                    break
                i += 1
                continue
            if _META_LINE.match(raw):
                if parts:
                    break
                i += 1
                continue
            parts.append(raw.strip())
            i += 1
        prompt = " ".join(parts).strip()
        if prompt:
            found.append(SheetImagePrompt(index=auto_index, prompt=prompt))
            auto_index += 1
    return found


def _normalize_lines(sheet_text: str) -> list[str]:
    return sheet_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
