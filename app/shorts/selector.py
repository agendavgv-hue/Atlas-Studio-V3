"""ShortsSelector — select relevant scenes only.

Never splits into shorts, never plans intro/outro/hook/CTA, never encodes or exports.
Production Sheet is preferred; image heuristics are fallback only.
Selection is deterministic for the same inputs.

Sheet structure is interpreted only via ``app.pipelines.sheet_prompts``.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.pipelines.sheet_prompts import (
    extract_image_prompt_entries,
    extract_sheet_duration_map,
    extract_sheet_durations,
    extract_sheet_labels,
)
from app.render.duration import natural_image_sort_key
from app.shorts.selection import SceneSelection, SelectedScene

_IMAGE_STEM_INDEX = re.compile(r"(\d+)")


class ShortsSelector:
    """Choose an ordered scene list from project assets."""

    def select(
        self,
        *,
        images: list[Path],
        sheet_text: str | None = None,
    ) -> SceneSelection:
        """Return a deterministic ``SceneSelection``."""
        ordered_images = sorted(
            [path for path in images if path.is_file()],
            key=natural_image_sort_key,
        )
        sheet = (sheet_text or "").strip()
        if sheet:
            sheet_selection = self._from_production_sheet(sheet, ordered_images)
            if sheet_selection is not None and sheet_selection.count > 0:
                return sheet_selection
        return self._from_images_fallback(ordered_images)

    def _from_production_sheet(
        self,
        sheet_text: str,
        ordered_images: list[Path],
    ) -> SceneSelection | None:
        entries = extract_image_prompt_entries(sheet_text)
        if not entries:
            return None

        duration_map = extract_sheet_duration_map(sheet_text)
        label_map = extract_sheet_labels(sheet_text)
        # Durations aligned to dense 1..N when every IMAGE 01..N declares Duration.
        full_durations = extract_sheet_durations(sheet_text, len(entries))

        scenes: list[SelectedScene] = []
        for position, entry in enumerate(entries, start=1):
            sheet_index = entry.index
            image = _match_image(ordered_images, sheet_index, position)
            if image is None:
                continue

            duration: float | None = None
            if full_durations is not None and sheet_index <= len(full_durations):
                # Prefer map by original IMAGE index when available.
                duration = duration_map.get(sheet_index, full_durations[position - 1])
            elif sheet_index in duration_map:
                duration = duration_map[sheet_index]

            label = label_map.get(sheet_index) or f"IMAGE {sheet_index:02d}"
            if sheet_index not in label_map and entry.prompt.strip():
                label = _short_label(entry.prompt)

            scenes.append(
                SelectedScene(
                    order=len(scenes) + 1,
                    image_path=str(image),
                    sheet_index=sheet_index,
                    sheet_ref=f"IMAGE {sheet_index:02d}",
                    duration_sec=duration,
                    label=label,
                )
            )

        if not scenes:
            return None

        return SceneSelection(
            scenes=tuple(scenes),
            source="production_sheet",
            rationale=(
                f"Selected {len(scenes)} scene(s) from the Production Sheet "
                f"(matched to project images)."
            ),
        )

    def _from_images_fallback(self, ordered_images: list[Path]) -> SceneSelection:
        scenes = tuple(
            SelectedScene(
                order=index,
                image_path=str(path),
                sheet_index=None,
                sheet_ref="",
                duration_sec=None,
                label=path.stem,
            )
            for index, path in enumerate(ordered_images, start=1)
        )
        if not scenes:
            return SceneSelection(
                scenes=(),
                source="images_fallback",
                rationale="No project images available for scene selection.",
            )
        return SceneSelection(
            scenes=scenes,
            source="images_fallback",
            rationale=(
                f"No suitable Production Sheet scenes — "
                f"selected {len(scenes)} image(s) in natural order."
            ),
        )


def _match_image(
    ordered_images: list[Path],
    sheet_index: int,
    position: int,
) -> Path | None:
    if not ordered_images:
        return None
    for path in ordered_images:
        stem_index = _stem_image_index(path)
        if stem_index == sheet_index:
            return path
    if 1 <= position <= len(ordered_images):
        return ordered_images[position - 1]
    return ordered_images[min(len(ordered_images), sheet_index) - 1]


def _stem_image_index(path: Path) -> int | None:
    matches = _IMAGE_STEM_INDEX.findall(path.stem)
    if not matches:
        return None
    try:
        return int(matches[-1])
    except ValueError:
        return None


def _short_label(prompt: str, *, limit: int = 48) -> str:
    text = " ".join(prompt.strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
