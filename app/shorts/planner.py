"""ShortsPlanner — turn SceneSelection into ShortsDefinitions.

Never selects scenes, encodes, exports, calls FFmpeg, or writes manifests.
Sprint 10 defaults to one definition; the API always returns list[ShortsDefinition].
Planning is deterministic for the same selection + settings.
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Protocol

from app.shorts.definition import (
    ShortsDefinition,
    ShortsOutputPlan,
    ShortsScene,
    ShortsSegmentPlaceholder,
    ShortsVoicePlan,
)
from app.shorts.naming import SHORTS_FOLDER, short_basename
from app.shorts.selection import SceneSelection, SelectedScene
from app.shorts.settings import ShortsSettings

# Fixed namespace so definition_id is stable across runs (not random uuid4).
_DEFINITION_NAMESPACE = uuid.UUID("7b2e9c41-6a8f-4d3b-9e15-0c4a8f2d91b0")


class ShortsAIPlanner(Protocol):
    """Optional future AI planner — replace or refine chunking without touching Generator."""

    def plan_chunks(
        self,
        scenes: tuple[SelectedScene, ...],
        settings: ShortsSettings,
    ) -> list[list[SelectedScene]]:
        """Return ordered scene groups (one group per short)."""


class ShortsPlanner:
    """Transforms selected scenes into one or more ShortsDefinitions."""

    def __init__(
        self,
        settings: ShortsSettings | None = None,
        *,
        ai_planner: ShortsAIPlanner | None = None,
    ) -> None:
        self._settings = settings or ShortsSettings()
        self._ai_planner = ai_planner

    def plan(
        self,
        selection: SceneSelection,
        *,
        voice_path: Path | None = None,
        voice_duration_sec: float | None = None,
    ) -> list[ShortsDefinition]:
        """Return a list of definitions (length >= 1 when scenes exist, else empty)."""
        scenes = tuple(selection.scenes)
        if not scenes:
            return []

        chunks = self._split_scenes(scenes)
        voice = self._voice_plan(voice_path)
        definitions: list[ShortsDefinition] = []

        for index, chunk in enumerate(chunks, start=1):
            planned_scenes, timing_source, total = self._assign_timing(
                chunk,
                voice_duration_sec=voice_duration_sec,
                chunk_count=len(chunks),
            )
            definition_id = _stable_definition_id(
                index=index,
                selection_source=selection.source,
                scenes=planned_scenes,
                settings=self._settings,
            )
            definitions.append(
                ShortsDefinition(
                    definition_id=definition_id,
                    index=index,
                    scenes=planned_scenes,
                    timing_source=timing_source,
                    total_duration_sec=total,
                    voice=voice,
                    output=self._output_plan(index),
                    title=_title_for_chunk(chunk, index),
                    rationale=_rationale(selection, index, len(chunks), timing_source),
                    intro=ShortsSegmentPlaceholder(kind="intro", enabled=False),
                    outro=ShortsSegmentPlaceholder(kind="outro", enabled=False),
                    hook=ShortsSegmentPlaceholder(kind="hook", enabled=False),
                    cta=ShortsSegmentPlaceholder(kind="cta", enabled=False),
                    exported=False,
                )
            )
        return definitions

    def _split_scenes(
        self,
        scenes: tuple[SelectedScene, ...],
    ) -> list[list[SelectedScene]]:
        if self._ai_planner is not None:
            chunks = self._ai_planner.plan_chunks(scenes, self._settings)
            cleaned = [list(group) for group in chunks if group]
            if cleaned:
                return cleaned

        max_shorts = max(1, int(self._settings.max_shorts))
        if max_shorts == 1 or len(scenes) <= 1:
            return [list(scenes)]

        # Deterministic equal-size chunks (future multi-short; unused when max_shorts=1).
        group_count = min(max_shorts, len(scenes))
        size = int(math.ceil(len(scenes) / group_count))
        chunks: list[list[SelectedScene]] = []
        for start in range(0, len(scenes), size):
            chunks.append(list(scenes[start : start + size]))
            if len(chunks) >= group_count:
                # Append any remainder to the last chunk for stability.
                if start + size < len(scenes):
                    chunks[-1].extend(scenes[start + size :])
                break
        return chunks

    def _assign_timing(
        self,
        chunk: list[SelectedScene],
        *,
        voice_duration_sec: float | None,
        chunk_count: int,
    ) -> tuple[list[ShortsScene], str, float]:
        default = max(0.5, float(self._settings.default_duration_sec))
        max_total = max(default, float(self._settings.max_duration_sec))

        if all(scene.duration_sec is not None and scene.duration_sec > 0 for scene in chunk):
            timing_source = "production_sheet"
            durations = [max(0.5, float(scene.duration_sec)) for scene in chunk]
        elif voice_duration_sec is not None and voice_duration_sec > 0:
            timing_source = "voice_equal_split"
            share = float(voice_duration_sec) / max(1, chunk_count)
            each = max(0.5, share / max(1, len(chunk)))
            durations = [each] * len(chunk)
        else:
            timing_source = "default_per_image"
            durations = [default] * len(chunk)

        total = sum(durations)
        if total > max_total and total > 0:
            scale = max_total / total
            durations = [max(0.5, value * scale) for value in durations]
            total = sum(durations)

        planned: list[ShortsScene] = []
        for position, (scene, duration) in enumerate(zip(chunk, durations), start=1):
            planned.append(
                ShortsScene(
                    index=position,
                    image_path=scene.image_path,
                    duration_sec=float(duration),
                    motion=self._settings.motion,
                    transition=self._settings.transition,
                    framing=self._settings.framing,
                    sheet_ref=scene.sheet_ref,
                    extras={"label": scene.label} if scene.label else {},
                )
            )
        return planned, timing_source, float(sum(durations))

    def _voice_plan(self, voice_path: Path | None) -> ShortsVoicePlan:
        if (
            self._settings.use_voice_when_available
            and voice_path is not None
            and voice_path.is_file()
        ):
            return ShortsVoicePlan(use_voice=True, voice_path=str(voice_path))
        return ShortsVoicePlan(use_voice=False, voice_path=None)

    def _output_plan(self, index: int) -> ShortsOutputPlan:
        return ShortsOutputPlan(
            filename=short_basename(index),
            folder=SHORTS_FOLDER,
            width=self._settings.width,
            height=self._settings.height,
            fps=self._settings.fps,
            profile=self._settings.profile,
            codec=self._settings.codec,
            preset=self._settings.preset,
            crf=self._settings.crf,
        )


def _stable_definition_id(
    *,
    index: int,
    selection_source: str,
    scenes: list[ShortsScene],
    settings: ShortsSettings,
) -> str:
    parts = [
        str(index),
        selection_source,
        settings.profile,
        settings.motion,
        settings.framing,
        settings.transition,
        f"{settings.width}x{settings.height}",
        str(settings.max_shorts),
    ]
    for scene in scenes:
        parts.append(
            f"{scene.index}:{scene.image_path}:{scene.duration_sec:.3f}:"
            f"{scene.sheet_ref}"
        )
    return str(uuid.uuid5(_DEFINITION_NAMESPACE, "|".join(parts)))


def _title_for_chunk(chunk: list[SelectedScene], index: int) -> str:
    if len(chunk) == 1 and chunk[0].label:
        return chunk[0].label
    if chunk and chunk[0].label:
        return f"Short {index:02d} — {chunk[0].label}"
    return f"Short {index:02d}"


def _rationale(
    selection: SceneSelection,
    index: int,
    total_defs: int,
    timing_source: str,
) -> str:
    if total_defs == 1:
        return (
            f"Planned one short from {selection.source} "
            f"({timing_source} timing)."
        )
    return (
        f"Planned short {index}/{total_defs} from {selection.source} "
        f"({timing_source} timing)."
    )
