"""FFmpegRenderer — builds and runs encode/assemble commands only.

Does not own timing policy, manifests, QC, or project intelligence.
All FFmpeg process execution goes through ``FFmpegProcess``.
"""

from __future__ import annotations

from pathlib import Path

from app.core.movie_settings import RenderProfileSpec
from app.providers.errors import ProviderError
from app.render.ffmpeg import FFmpegProcess
from app.render.motion import scene_video_filter
from app.render.timeline import TimelineScene


class FFmpegRenderer:
    """Scene encode + final concat/mux. Orchestration stays in RenderService."""

    def __init__(self, ffmpeg: FFmpegProcess) -> None:
        self._ffmpeg = ffmpeg

    @property
    def ffmpeg(self) -> FFmpegProcess:
        return self._ffmpeg

    def render_scene(
        self,
        scene: TimelineScene,
        out_path: Path,
        profile: RenderProfileSpec,
    ) -> None:
        """Encode one still image into a silent scene MP4."""
        vf = scene_video_filter(
            width=profile.width,
            height=profile.height,
            fps=profile.fps,
            duration_sec=scene.duration_sec,
            motion=scene.motion,
        )
        args = [
            "-y",
            "-loop",
            "1",
            "-i",
            str(scene.image_path),
            "-t",
            f"{scene.duration_sec:.3f}",
            "-vf",
            vf,
            "-c:v",
            profile.codec,
            "-preset",
            profile.preset,
            "-crf",
            str(profile.crf),
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out_path),
        ]
        self._ffmpeg.run(args)

    def export_final(
        self,
        scene_files: list[Path],
        voice_path: Path | None,
        final_path: Path,
        profile: RenderProfileSpec,
    ) -> None:
        """Concatenate scene clips and optionally mux narration audio."""
        if not scene_files:
            raise ProviderError("No scene files to export.")

        list_file = final_path.parent / ".atlas_concat.txt"
        lines = [f"file '{_ffmpeg_path(path)}'" for path in scene_files]
        list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Concat demuxer. Fade/crossfade share concat today;
        # xfade filter_complex can refine transitions later without API changes.
        try:
            if voice_path is not None and voice_path.is_file():
                args = [
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_file),
                    "-i",
                    str(voice_path),
                    "-c:v",
                    profile.codec,
                    "-preset",
                    profile.preset,
                    "-crf",
                    str(profile.crf),
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-pix_fmt",
                    "yuv420p",
                    "-shortest",
                    str(final_path),
                ]
            else:
                args = [
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_file),
                    "-c",
                    "copy",
                    str(final_path),
                ]
            self._ffmpeg.run(args)
        finally:
            list_file.unlink(missing_ok=True)


def _ffmpeg_path(path: Path) -> str:
    # Concat demuxer on Windows needs forward slashes / escaped quotes.
    return str(path.resolve()).replace("\\", "/").replace("'", r"'\''")
