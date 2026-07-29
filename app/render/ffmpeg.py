"""FFmpeg process abstraction — only module that spawns FFmpeg."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.providers.errors import ProviderError


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
        probe = self._probe or self._sibling_probe(self.resolve())
        if probe is None or not probe.is_file():
            return None
        args = [
            str(probe),
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(path),
        ]
        try:
            result = self._run(args, timeout=60)
        except ProviderError:
            return None
        try:
            payload = json.loads(result.stdout or "{}")
            duration = float((payload.get("format") or {}).get("duration"))
            if duration > 0:
                return duration
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return None

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
