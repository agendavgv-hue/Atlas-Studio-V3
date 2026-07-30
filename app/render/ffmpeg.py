"""FFmpeg process abstraction — only module that spawns FFmpeg."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.providers.errors import ProviderError


@dataclass(frozen=True)
class MediaProbe:
    """Lightweight media summary from ffprobe (or test doubles)."""

    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    has_video: bool = False
    has_audio: bool = False


class FFmpegProcess:
    """Resolve, validate, and run FFmpeg/ffprobe. Supports cooperative cancel."""

    def __init__(self, configured_path: str = "") -> None:
        self._configured = (configured_path or "").strip()
        self._binary: Path | None = None
        self._probe: Path | None = None
        self._active: subprocess.Popen[str] | None = None
        self._cancel_requested = False

    def resolve(self) -> Path:
        if self._binary is not None:
            return self._binary
        candidates: list[Path] = []
        if self._configured:
            candidates.append(Path(self._configured).expanduser())
        which = shutil.which("ffmpeg")
        if which:
            candidates.append(Path(which))
        for path in candidates:
            if path.is_file():
                self._binary = path.resolve()
                self._probe = self._sibling_probe(self._binary)
                return self._binary
        raise ProviderError(
            "FFmpeg was not found. Install FFmpeg and set its path in Settings → Movie, "
            "or add ffmpeg to your system PATH."
        )

    def validate(self) -> str:
        binary = self.resolve()
        result = self._run([str(binary), "-version"], timeout=30)
        first = (result.stdout or result.stderr or "").splitlines()
        line = first[0].strip() if first else "FFmpeg OK"
        return f"FFmpeg ready — {line}"

    def request_cancel(self) -> None:
        self._cancel_requested = True
        active = self._active
        if active is not None and active.poll() is None:
            try:
                active.terminate()
            except OSError:
                pass

    def is_cancel_requested(self) -> bool:
        return self._cancel_requested

    def reset_cancel(self) -> None:
        self._cancel_requested = False

    def probe_duration(self, path: Path) -> float | None:
        """Return media duration in seconds, or None if unknown."""
        info = self.probe_media(path)
        if info is None:
            return None
        return info.duration_sec

    def probe_media(self, path: Path) -> MediaProbe | None:
        """Return stream/format summary, or None if probing is unavailable."""
        if not path.is_file():
            return None
        probe = self._probe
        if probe is None:
            try:
                probe = self._sibling_probe(self.resolve())
                self._probe = probe
            except ProviderError:
                return None
        if probe is None or not probe.is_file():
            return None
        args = [
            str(probe),
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            result = self._run(args, timeout=60)
        except ProviderError:
            return None
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            return None
        return _media_probe_from_payload(payload)

    def run(self, args: list[str], *, timeout: float | None = 3600) -> subprocess.CompletedProcess[str]:
        binary = self.resolve()
        if self._cancel_requested:
            raise ProviderError("FFmpeg cancelled.")
        command = [str(binary), *args]
        try:
            self._active = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert self._active is not None
            try:
                stdout, stderr = self._active.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                self._active.kill()
                raise ProviderError("FFmpeg timed out.") from exc
            code = self._active.returncode or 0
        finally:
            self._active = None

        if self._cancel_requested:
            raise ProviderError("FFmpeg cancelled.")
        if code != 0:
            detail = (stderr or stdout or "").strip()
            tail = detail[-400:] if detail else f"exit code {code}"
            raise ProviderError(f"FFmpeg failed: {tail}")
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    def _run(self, command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ProviderError("FFmpeg executable is missing.") from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderError("FFmpeg timed out.") from exc

    @staticmethod
    def _sibling_probe(ffmpeg: Path) -> Path | None:
        name = "ffprobe.exe" if ffmpeg.suffix.casefold() == ".exe" else "ffprobe"
        sibling = ffmpeg.with_name(name)
        if sibling.is_file():
            return sibling
        which = shutil.which("ffprobe")
        return Path(which) if which else None


def _media_probe_from_payload(payload: dict) -> MediaProbe:
    duration_sec: float | None = None
    fmt = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    try:
        duration_sec = float(fmt.get("duration"))
        if duration_sec <= 0:
            duration_sec = None
    except (TypeError, ValueError):
        duration_sec = None

    width = height = None
    fps: float | None = None
    has_video = False
    has_audio = False
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        codec_type = str(stream.get("codec_type") or "").casefold()
        if codec_type == "video":
            has_video = True
            try:
                width = int(stream.get("width"))
                height = int(stream.get("height"))
            except (TypeError, ValueError):
                pass
            fps = _parse_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
        elif codec_type == "audio":
            has_audio = True
    return MediaProbe(
        duration_sec=duration_sec,
        width=width,
        height=height,
        fps=fps,
        has_video=has_video,
        has_audio=has_audio,
    )


def _parse_fps(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text == "0/0":
        return None
    if "/" in text:
        num_s, den_s = text.split("/", 1)
        try:
            num = float(num_s)
            den = float(den_s)
        except ValueError:
            return None
        if den == 0:
            return None
        return num / den
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if parsed > 0 else None
