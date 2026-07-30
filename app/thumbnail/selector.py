"""ThumbnailSelector — decide what becomes the thumbnail.

Never generates, exports, mutates images, calls providers, or writes manifests.
Future AI scoring plugs in via ``ThumbnailScorer`` without changing Generator/Exporter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.settings import ThumbnailSettings


@dataclass(frozen=True)
class SelectionGenerationSettings:
    """Provider-agnostic generation snapshot carried in the decision.

    The Service later maps this into an ``ImageGenerationRequest``.
    The Selector never talks to providers.
    """

    width: int = 1280
    height: int = 720
    seed: int = -1
    model: str = ""
    steps: int = 0
    cfg_scale: float = 0.0
    sampler: str = ""


@dataclass(frozen=True)
class SelectionDecision:
    """Immutable selection outcome for one thumbnail run."""

    mode: ThumbnailMode
    source_image_path: Path | None
    prompt: str
    negative_prompt: str
    generation: SelectionGenerationSettings
    rationale: str


class ThumbnailScorer(Protocol):
    """Optional future AI scorer — pick among image paths.

    Sprint 9 does not implement scoring; inject a scorer later for Mode 4
    (or to refine Mode 3) without redesigning the pipeline.
    """

    def pick(self, images: list[Path], *, prompt: str = "") -> Path | None:
        """Return the preferred image path, or None to fall back to heuristics."""


class ThumbnailSelector:
    """Chooses mode, source image, and/or prompts for the Generator."""

    def __init__(
        self,
        settings: ThumbnailSettings | None = None,
        *,
        scorer: ThumbnailScorer | None = None,
    ) -> None:
        self._settings = settings or ThumbnailSettings()
        self._scorer = scorer

    def select(
        self,
        *,
        images: list[Path],
        thumbnail_prompt: str = "",
        negative_prompt: str = "",
        project_title: str = "",
    ) -> SelectionDecision:
        """Return a ``SelectionDecision`` for the current project inputs."""
        mode = self._resolve_mode(thumbnail_prompt=thumbnail_prompt, images=images)
        generation = SelectionGenerationSettings(
            width=max(16, int(self._settings.width)),
            height=max(16, int(self._settings.height)),
            seed=int(self._settings.seed),
            model=(self._settings.model or "").strip(),
            steps=max(0, int(self._settings.steps)),
            cfg_scale=float(self._settings.cfg_scale),
            sampler=(self._settings.sampler or "").strip(),
        )
        prompt = (thumbnail_prompt or "").strip()
        negative = (negative_prompt or "").strip()

        if mode is ThumbnailMode.GENERATE:
            if not prompt and project_title.strip():
                prompt = project_title.strip()
            return SelectionDecision(
                mode=mode,
                source_image_path=None,
                prompt=prompt,
                negative_prompt=negative,
                generation=generation,
                rationale=self._generate_rationale(prompt),
            )

        chosen = self._choose_image(images, prompt=prompt, mode=mode)
        return SelectionDecision(
            mode=mode,
            source_image_path=chosen,
            prompt=prompt,
            negative_prompt=negative,
            generation=generation,
            rationale=self._select_rationale(mode, chosen, images),
        )

    def _resolve_mode(self, *, thumbnail_prompt: str, images: list[Path]) -> ThumbnailMode:
        configured = (self._settings.mode or ThumbnailMode.SELECT.value).strip().casefold()
        try:
            mode = ThumbnailMode(configured)
        except ValueError:
            mode = ThumbnailMode.SELECT

        if mode is ThumbnailMode.AI_SCORED:
            # Reserved — behave like candidates/select until a scorer exists.
            return ThumbnailMode.AI_SCORED if self._scorer is not None else ThumbnailMode.CANDIDATES

        if mode is ThumbnailMode.GENERATE:
            return ThumbnailMode.GENERATE

        if mode is ThumbnailMode.CANDIDATES:
            return ThumbnailMode.CANDIDATES

        # SELECT default — fall back to generate when there are no images but a prompt exists.
        if not images and (thumbnail_prompt or "").strip():
            return ThumbnailMode.GENERATE
        return ThumbnailMode.SELECT

    def _choose_image(
        self,
        images: list[Path],
        *,
        prompt: str,
        mode: ThumbnailMode,
    ) -> Path | None:
        existing = [path for path in images if path.is_file()]
        if not existing:
            return None

        if mode is ThumbnailMode.AI_SCORED and self._scorer is not None:
            picked = self._scorer.pick(existing, prompt=prompt)
            if picked is not None and picked in existing:
                return picked

        # Mode 3 / select heuristic: middle scene (stable, no disk candidates).
        return existing[len(existing) // 2]

    @staticmethod
    def _generate_rationale(prompt: str) -> str:
        if prompt:
            return "Generate a new thumbnail from the prepared prompt."
        return "Generate mode selected; prompt is empty (pipeline must supply one)."

    @staticmethod
    def _select_rationale(
        mode: ThumbnailMode,
        chosen: Path | None,
        images: list[Path],
    ) -> str:
        if chosen is None:
            return "No project images available to select."
        if mode is ThumbnailMode.AI_SCORED:
            return f"AI-scored selection chose {chosen.name}."
        if mode is ThumbnailMode.CANDIDATES:
            return (
                f"Chose middle image {chosen.name} "
                f"among {len([p for p in images if p.is_file()])} candidate source(s)."
            )
        return f"Selected project image {chosen.name}."
