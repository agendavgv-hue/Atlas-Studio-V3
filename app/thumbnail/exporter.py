"""ThumbnailExporter — write strategy, prompt, hook, variants, primary PNG.

Does not select sources, call providers, or invent prompts.
Atlas composites logo/frame/text after AI generation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.thumbnail.brand_overlay import apply_brand_overlays
from app.thumbnail.intelligence.branding import LogoPlacement
from app.thumbnail.naming import (
    thumbnail_critique_path,
    thumbnail_path,
    thumbnail_prompt_path,
    thumbnail_strategy_path,
    thumbnail_title_path,
    thumbnail_variant_path,
)
from app.thumbnail.text_overlay import render_thumbnail_text
from app.thumbnail.thumbnail_director import ThumbnailStrategy


@dataclass(frozen=True)
class ThumbnailExportResult:
    """Outcome of exporting the intelligent thumbnail package."""

    primary_path: Path
    title_path: Path
    strategy_path: Path | None
    prompt_path: Path | None
    critique_path: Path | None
    variant_paths: tuple[Path, ...]
    bytes_written: int

    @property
    def path(self) -> Path:
        """Backward-compatible alias for the primary thumbnail path."""
        return self.primary_path


class ThumbnailExporter:
    """Project-facing writer for the Intelligent Thumbnail Engine outputs."""

    def export_package(
        self,
        project_dir: Path,
        *,
        hook: str,
        variants: list[tuple[str, bytes]],
        primary_variant_id: str = "A",
        strategy: ThumbnailStrategy | None = None,
        primary_prompt: str = "",
        critique_reports: list[dict[str, Any]] | None = None,
        channel_name: str = "",
        logo_path: Path | None = None,
        frame_path: Path | None = None,
        logo_placement: LogoPlacement | None = None,
        text_fill_hex: str = "",
        text_outline_hex: str = "",
        font_family: str = "",
        max_words: int = 0,
        text_align_left: bool | None = None,
    ) -> ThumbnailExportResult:
        """Write strategy/prompt/title + four variant PNGs + branded primary."""
        if not variants:
            raise ValueError("Cannot export thumbnails without variant images.")
        hook_text = (hook or "").strip()
        if not hook_text:
            raise ValueError("Cannot export thumbnails without a hook (thumbnail_title).")

        out_dir = thumbnail_title_path(project_dir).parent
        out_dir.mkdir(parents=True, exist_ok=True)

        strategy_path: Path | None = None
        if strategy is not None:
            strategy_path = thumbnail_strategy_path(project_dir)
            strategy.write_json(strategy_path)

        prompt_path: Path | None = None
        prompt_text = (primary_prompt or "").strip()
        if prompt_text:
            prompt_path = thumbnail_prompt_path(project_dir)
            prompt_path.write_text(prompt_text + "\n", encoding="utf-8")

        critique_path: Path | None = None
        if critique_reports is not None:
            critique_path = thumbnail_critique_path(project_dir)
            critique_path.write_text(
                json.dumps({"variants": critique_reports}, indent=2) + "\n",
                encoding="utf-8",
            )

        title_path = thumbnail_title_path(project_dir)
        title_path.write_text(hook_text + "\n", encoding="utf-8")

        written = 0
        paths: list[Path] = []
        by_id: dict[str, bytes] = {}
        for variant_id, image_png in variants:
            if not image_png:
                raise ValueError(f"Cannot export empty thumbnail variant {variant_id}.")
            path = thumbnail_variant_path(project_dir, variant_id)
            path.write_bytes(image_png)
            written += len(image_png)
            paths.append(path)
            by_id[variant_id.upper()] = image_png

        primary_bytes = by_id.get(primary_variant_id.upper()) or variants[0][1]
        # 1) Frame + logo from Brand Kit (never AI-generated).
        primary_bytes = apply_brand_overlays(
            primary_bytes,
            logo_path=logo_path,
            frame_path=frame_path,
            placement=logo_placement,
        )
        # 2) Atlas typography — never rely on the image model for text.
        primary_bytes = render_thumbnail_text(
            primary_bytes,
            hook_text,
            channel_name=channel_name,
            fill_hex=text_fill_hex,
            outline_hex=text_outline_hex,
            font_family=font_family,
            align_left=text_align_left,
            max_words=max_words,
        )
        primary = thumbnail_path(project_dir)
        primary.write_bytes(primary_bytes)
        written += len(primary_bytes)

        return ThumbnailExportResult(
            primary_path=primary,
            title_path=title_path,
            strategy_path=strategy_path,
            prompt_path=prompt_path,
            critique_path=critique_path,
            variant_paths=tuple(paths),
            bytes_written=written,
        )

    def export_png(self, project_dir: Path, image_png: bytes) -> ThumbnailExportResult:
        """Legacy single-PNG export (select mode)."""
        if not image_png:
            raise ValueError("Cannot export an empty thumbnail image.")
        path = thumbnail_path(project_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_png)
        title_path = thumbnail_title_path(project_dir)
        return ThumbnailExportResult(
            primary_path=path,
            title_path=title_path,
            strategy_path=None,
            prompt_path=None,
            critique_path=None,
            variant_paths=(path,),
            bytes_written=len(image_png),
        )
