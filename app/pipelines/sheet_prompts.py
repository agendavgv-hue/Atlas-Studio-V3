"""Extract image prompts from production sheets — format-tolerant (V2 / V3 / renamed)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SheetImagePrompt:
    """One image prompt discovered in a production sheet (1-based index)."""

    index: int
    prompt: str


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


def extract_image_prompts(sheet_text: str) -> list[SheetImagePrompt]:
    """Discover every image prompt without requiring exact sheet formatting."""
    lines = sheet_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    found: list[SheetImagePrompt] = []
    i = 0
    auto_index = 1

    while i < len(lines):
        line = lines[i]
        header = _IMAGE_HEADER.match(line)
        if header:
            index = int(header.group(1))
            prompt, consumed = _read_prompt_block(lines, i + 1)
            if prompt:
                found.append(SheetImagePrompt(index=index, prompt=prompt))
            i += consumed + 1
            continue

        inline = _IMAGE_PROMPT_INLINE.match(line)
        if inline:
            rest = inline.group(1).strip()
            if rest:
                found.append(SheetImagePrompt(index=auto_index, prompt=rest))
                auto_index += 1
                i += 1
                continue
            prompt, consumed = _read_prompt_block(lines, i + 1, require_label=False)
            if prompt:
                found.append(SheetImagePrompt(index=auto_index, prompt=prompt))
                auto_index += 1
            i += consumed + 1
            continue

        i += 1

    # Re-number densely if indexes collide / missing while preserving order.
    if not found:
        return []
    return [
        SheetImagePrompt(index=position, prompt=item.prompt)
        for position, item in enumerate(found, start=1)
    ]


def _read_prompt_block(
    lines: list[str],
    start: int,
    *,
    require_label: bool = True,
) -> tuple[str, int]:
    """Return (prompt_text, lines_consumed from start)."""
    if start >= len(lines):
        return "", 0

    cursor = start
    if require_label:
        label = _PROMPT_LABEL.match(lines[cursor])
        if label:
            first = label.group(1).strip()
            cursor += 1
            if first:
                return first, cursor - start
        else:
            # Allow prompt text immediately under IMAGE NN without "Prompt:" label.
            require_label = False

    parts: list[str] = []
    while cursor < len(lines):
        raw = lines[cursor]
        if _IMAGE_HEADER.match(raw) or _IMAGE_PROMPT_INLINE.match(raw):
            break
        if not raw.strip():
            if parts:
                break
            cursor += 1
            continue
        # Stop at next section-looking labels.
        if re.match(r"^\s*(Scene|Narration|Visual|Duration)\s*:", raw, re.I) and parts:
            break
        parts.append(raw.strip())
        cursor += 1

    return " ".join(parts).strip(), cursor - start
