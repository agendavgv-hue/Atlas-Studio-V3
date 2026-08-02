"""Public Style DNA package exports."""

from app.thumbnail.style_dna.analyzer import ThumbnailStyleAnalyzer
from app.thumbnail.style_dna.layout import TextLayoutSpec, split_hook_lines, text_layout_from_dna
from app.thumbnail.style_dna.models import ReferenceStyleSample, ThumbnailStyleDNA
from app.thumbnail.style_dna.store import (
    STYLE_PROFILE_BASENAME,
    read_style_dna,
    write_style_dna,
)

__all__ = [
    "STYLE_PROFILE_BASENAME",
    "ReferenceStyleSample",
    "TextLayoutSpec",
    "ThumbnailStyleAnalyzer",
    "ThumbnailStyleDNA",
    "ThumbnailStyleDNAService",
    "read_style_dna",
    "split_hook_lines",
    "text_layout_from_dna",
    "write_style_dna",
]


def __getattr__(name: str):
    if name == "ThumbnailStyleDNAService":
        from app.thumbnail.style_dna.service import ThumbnailStyleDNAService

        return ThumbnailStyleDNAService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
