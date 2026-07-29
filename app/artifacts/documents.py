"""Read script-like documents without depending on a single filename or extension."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


def read_document_text(path: Path) -> str:
    """Return plain text from txt/md/docx/rtf (and utf-8 fallback for others)."""
    suffix = path.suffix.casefold()
    if suffix in {".txt", ".md", ".markdown", ".text"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".rtf":
        return _read_rtf(path)
    # V2 sometimes uses odd extensions; try utf-8 text.
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise OSError(f"Unsupported or binary document: {path.name}") from exc


def _read_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise OSError(f"Invalid DOCX file: {path.name}") from exc
    root = ElementTree.fromstring(xml_bytes)
    parts: list[str] = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "t" and node.text:
            parts.append(node.text)
        elif tag == "tab":
            parts.append("\t")
        elif tag in {"br", "cr"}:
            parts.append("\n")
        elif tag == "p":
            parts.append("\n")
    text = "".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + ("\n" if text.strip() else "")


def _read_rtf(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    # Strip groups and control words — good enough for narration scripts.
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + ("\n" if text.strip() else "")
