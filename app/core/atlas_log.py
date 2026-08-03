"""Project-scoped Atlas production log (append-only)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, Signal


class AtlasLog(QObject):
    """Writes timestamped lines to ``atlas.log`` inside a project folder."""

    line_written = Signal(str)

    LOG_NAME = "atlas.log"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._project_dir: Path | None = None

    def bind_project(self, project_dir: Path | None) -> None:
        self._project_dir = project_dir.expanduser().resolve() if project_dir else None

    def write(self, message: str) -> None:
        text = (message or "").strip()
        if not text:
            return
        stamp = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
        line = f"[{stamp}] {text}"
        self.line_written.emit(line)
        folder = self._project_dir
        if folder is None:
            return
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / self.LOG_NAME
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass
