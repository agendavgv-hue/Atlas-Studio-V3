"""Automatic project numbering: ``001 - Title``."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Standard form: ``001 - Title`` (dash required when a title is present).
_NUMBERED_NAME = re.compile(r"^\s*(\d+)\s*[-–—]\s*(.+)$", re.UNICODE)
_PURE_NUMBER = re.compile(r"^\s*(\d+)\s*$")


def parse_project_number(folder_name: str) -> int | None:
    """Return the leading project number if present, else ``None``."""
    raw = folder_name.strip()
    numbered = _NUMBERED_NAME.match(raw)
    if numbered:
        return int(numbered.group(1))
    pure = _PURE_NUMBER.match(raw)
    if pure:
        return int(pure.group(1))
    return None


def project_title(folder_name: str) -> str:
    """Human title for generation — strips ``001 - `` numbering when present."""
    raw = folder_name.strip()
    numbered = _NUMBERED_NAME.match(raw)
    if numbered:
        return numbered.group(2).strip()
    return raw


def next_project_number(existing_folder_names: Iterable[str]) -> int:
    numbers = [n for name in existing_folder_names if (n := parse_project_number(name)) is not None]
    return (max(numbers) + 1) if numbers else 1


def format_project_folder_name(number: int, title: str) -> str:
    return f"{number:03d} - {title.strip()}"


def allocate_project_folder_name(title: str, existing_folder_names: Iterable[str]) -> str:
    number = next_project_number(existing_folder_names)
    return format_project_folder_name(number, title)
