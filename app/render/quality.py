"""QualityController — validate rendered movie output only.

Never repairs, re-encodes, deletes, or mutates project files.
RenderService consumes ``QualityReport`` and decides the pipeline outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.render.ffmpeg import FFmpegProcess, MediaProbe


@dataclass(frozen=True)
class QualityReport:
    """Immutable QC result. Safe to embed later in render_manifest.json."""

    passed: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "checks": dict(self.checks),
        }


class QualityController:
    """Independent validator for a finished video file."""

    def __init__(
        self,
        ffmpeg: FFmpegProcess,
        *,
        duration_tolerance_sec: float = 1.0,
        fps_tolerance: float = 1.0,
    ) -> None:
        self._ffmpeg = ffmpeg
        self._duration_tolerance_sec = max(0.1, float(duration_tolerance_sec))
        self._fps_tolerance = max(0.1, float(fps_tolerance))

    def validate(
        self,
        video_path: Path,
        *,
        expected_width: int,
        expected_height: int,
        expected_fps: int,
        expected_duration_sec: float | None = None,
        require_audio: bool = False,
    ) -> QualityReport:
        """Inspect ``video_path``. Does not modify the file or project."""
        warnings: list[str] = []
        errors: list[str] = []
        checks: dict[str, Any] = {
            "path": str(video_path),
            "expected_width": expected_width,
            "expected_height": expected_height,
            "expected_fps": expected_fps,
            "expected_duration_sec": expected_duration_sec,
            "require_audio": require_audio,
        }

        if not video_path.is_file():
            errors.append(f"Output video is missing: {video_path}")
            return QualityReport(passed=False, warnings=warnings, errors=errors, checks=checks)

        try:
            size = video_path.stat().st_size
        except OSError as exc:
            errors.append(f"Cannot read output video: {exc}")
            return QualityReport(passed=False, warnings=warnings, errors=errors, checks=checks)

        checks["size_bytes"] = size
        if size <= 0:
            errors.append("Output video file is empty.")
            return QualityReport(passed=False, warnings=warnings, errors=errors, checks=checks)

        probe = self._ffmpeg.probe_media(video_path)
        checks["probed"] = probe is not None
        if probe is None:
            warnings.append(
                "Media probe unavailable — skipped stream/resolution/duration checks."
            )
            return QualityReport(
                passed=len(errors) == 0,
                warnings=warnings,
                errors=errors,
                checks=checks,
            )

        self._apply_probe_checks(
            probe,
            warnings=warnings,
            errors=errors,
            checks=checks,
            expected_width=expected_width,
            expected_height=expected_height,
            expected_fps=expected_fps,
            expected_duration_sec=expected_duration_sec,
            require_audio=require_audio,
        )
        return QualityReport(
            passed=len(errors) == 0,
            warnings=warnings,
            errors=errors,
            checks=checks,
        )

    def _apply_probe_checks(
        self,
        probe: MediaProbe,
        *,
        warnings: list[str],
        errors: list[str],
        checks: dict[str, Any],
        expected_width: int,
        expected_height: int,
        expected_fps: int,
        expected_duration_sec: float | None,
        require_audio: bool,
    ) -> None:
        checks["has_video"] = probe.has_video
        checks["has_audio"] = probe.has_audio
        checks["width"] = probe.width
        checks["height"] = probe.height
        checks["fps"] = probe.fps
        checks["duration_sec"] = probe.duration_sec

        if not probe.has_video:
            errors.append("Output has no video stream.")

        if require_audio and not probe.has_audio:
            errors.append("Narration was planned but output has no audio stream.")

        if probe.width is not None and probe.width != expected_width:
            errors.append(
                f"Unexpected width {probe.width} (expected {expected_width})."
            )
        elif probe.width is None:
            warnings.append("Could not verify output width.")

        if probe.height is not None and probe.height != expected_height:
            errors.append(
                f"Unexpected height {probe.height} (expected {expected_height})."
            )
        elif probe.height is None:
            warnings.append("Could not verify output height.")

        if probe.fps is not None:
            if abs(probe.fps - float(expected_fps)) > self._fps_tolerance:
                warnings.append(
                    f"FPS {probe.fps:.3f} differs from expected {expected_fps}."
                )
        else:
            warnings.append("Could not verify output FPS.")

        if expected_duration_sec is not None and expected_duration_sec > 0:
            if probe.duration_sec is None:
                warnings.append("Could not verify output duration.")
            elif abs(probe.duration_sec - expected_duration_sec) > self._duration_tolerance_sec:
                warnings.append(
                    f"Duration {probe.duration_sec:.2f}s differs from planned "
                    f"{expected_duration_sec:.2f}s "
                    f"(tolerance {self._duration_tolerance_sec:.2f}s)."
                )
