"""ShortsGenerator — render exactly one ShortsDefinition.

Uses existing ``FFmpegRenderer`` / ``FFmpegProcess``. Never selects, plans,
exports to the project folder, or writes manifests.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.core.movie_settings import RenderProfileSpec
from app.pipelines.context import PipelineContext
from app.providers.errors import ProviderError
from app.render.ffmpeg import FFmpegProcess
from app.render.renderer import FFmpegRenderer
from app.render.timeline import TimelineScene
from app.shorts.definition import ShortsDefinition


@dataclass(frozen=True)
class ShortsGenerationResult:
    """Assembled video payload for ShortsExporter."""

    definition_id: str
    video_bytes: bytes


class ShortsGenerator:
    """Build the timeline described by a ShortsDefinition and render it."""

    def __init__(
        self,
        ffmpeg: FFmpegProcess | None = None,
        *,
        renderer: FFmpegRenderer | None = None,
    ) -> None:
        self._ffmpeg = ffmpeg or FFmpegProcess()
        self._renderer = renderer or FFmpegRenderer(self._ffmpeg)

    @property
    def renderer(self) -> FFmpegRenderer:
        return self._renderer

    def generate(
        self,
        definition: ShortsDefinition,
        context: PipelineContext,
        profile: RenderProfileSpec,
    ) -> ShortsGenerationResult:
        """Render ``definition`` to MP4 bytes. Does not write ``short/short_NN.mp4``."""
        del context  # reserved for future work-dir / branding hooks
        if not definition.scenes:
            raise ProviderError(
                f"ShortsDefinition {definition.definition_id} has no scenes to render."
            )

        timeline_scenes = self._timeline_scenes(definition)
        voice_path = self._voice_path(definition)

        with tempfile.TemporaryDirectory(prefix="atlas_short_") as tmp:
            work = Path(tmp)
            scene_files: list[Path] = []
            for scene in timeline_scenes:
                if not scene.image_path.is_file():
                    raise ProviderError(
                        f"Short scene image is missing: {scene.image_path}"
                    )
                out = work / f"scene_{scene.index:02d}.mp4"
                self._renderer.render_scene(scene, out, profile)
                scene_files.append(out)

            assembled = work / "assembled.mp4"
            self._renderer.export_final(scene_files, voice_path, assembled, profile)
            if not assembled.is_file() or assembled.stat().st_size <= 0:
                raise ProviderError("Short render produced an empty video.")
            return ShortsGenerationResult(
                definition_id=definition.definition_id,
                video_bytes=assembled.read_bytes(),
            )

    @staticmethod
    def _timeline_scenes(definition: ShortsDefinition) -> list[TimelineScene]:
        """Map definition scenes only — ignore disabled intro/outro/hook/CTA placeholders."""
        # Placeholders remain reserved; Generator does not invent structure for them.
        scenes: list[TimelineScene] = []
        for item in definition.scenes:
            scenes.append(
                TimelineScene(
                    index=item.index,
                    image_path=Path(item.image_path),
                    duration_sec=float(item.duration_sec),
                    motion=item.motion or "none",
                    transition=item.transition or "cut",
                )
            )
        return scenes

    @staticmethod
    def _voice_path(definition: ShortsDefinition) -> Path | None:
        if not definition.voice.use_voice:
            return None
        raw = definition.voice.voice_path
        if not raw:
            return None
        path = Path(raw)
        return path if path.is_file() else None
