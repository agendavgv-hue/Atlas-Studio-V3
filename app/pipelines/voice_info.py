"""Voice file size / duration helpers for Workspace display."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceFileInfo:
    path: Path
    size_bytes: int
    duration_ms: int | None = None

    @property
    def size_label(self) -> str:
        return format_file_size(self.size_bytes)

    @property
    def duration_label(self) -> str:
        if self.duration_ms is None or self.duration_ms < 0:
            return "—"
        return format_duration_ms(self.duration_ms)

    @property
    def summary(self) -> str:
        return f"Duration {self.duration_label}  ·  Size {self.size_label}"


def format_file_size(size_bytes: int) -> str:
    value = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{size_bytes} B"


def format_duration_ms(duration_ms: int) -> str:
    total_seconds = max(0, int(round(duration_ms / 1000.0)))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def voice_file_info(path: Path, *, duration_ms: int | None = None) -> VoiceFileInfo | None:
    if not path.is_file():
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    return VoiceFileInfo(path=path, size_bytes=size, duration_ms=duration_ms)
