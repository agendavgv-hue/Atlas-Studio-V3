"""Permanent sidebar Status card — live pipeline progress."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


def _format_seconds(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class StatusCard(QFrame):
    """Prominent live status panel for the left sidebar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarStatusCard")

        title = QLabel("STATUS")
        title.setObjectName("SidebarStatusTitle")

        self._task_caption = QLabel("Current Task")
        self._task_caption.setObjectName("SidebarStatusCaption")
        self._task = QLabel("Ready")
        self._task.setObjectName("SidebarStatusTask")
        self._task.setWordWrap(True)

        self._progress_caption = QLabel("Progress")
        self._progress_caption.setObjectName("SidebarStatusCaption")
        self._progress_text = QLabel("—")
        self._progress_text.setObjectName("SidebarStatusValue")

        self._bar = QProgressBar()
        self._bar.setObjectName("SidebarStatusBar")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(18)

        self._item_caption = QLabel("Current Item")
        self._item_caption.setObjectName("SidebarStatusCaption")
        self._item = QLabel("—")
        self._item.setObjectName("SidebarStatusValue")
        self._item.setWordWrap(True)

        self._elapsed_caption = QLabel("Elapsed Time")
        self._elapsed_caption.setObjectName("SidebarStatusCaption")
        self._elapsed = QLabel("—")
        self._elapsed.setObjectName("SidebarStatusValue")

        self._eta_caption = QLabel("ETA")
        self._eta_caption.setObjectName("SidebarStatusCaption")
        self._eta = QLabel("—")
        self._eta.setObjectName("SidebarStatusValue")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(4)
        layout.addWidget(title)
        layout.addSpacing(6)
        layout.addWidget(self._task_caption)
        layout.addWidget(self._task)
        layout.addSpacing(8)
        layout.addWidget(self._progress_caption)
        layout.addWidget(self._progress_text)
        layout.addWidget(self._bar)
        layout.addSpacing(8)
        layout.addWidget(self._item_caption)
        layout.addWidget(self._item)
        layout.addSpacing(6)
        layout.addWidget(self._elapsed_caption)
        layout.addWidget(self._elapsed)
        layout.addSpacing(4)
        layout.addWidget(self._eta_caption)
        layout.addWidget(self._eta)

        self.reset()

    def reset(self) -> None:
        self._task.setText("Ready")
        self._progress_text.setText("—")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._item.setText("—")
        self._elapsed.setText("—")
        self._eta.setText("—")

    def set_from_status_text(self, text: str) -> None:
        """Fallback when only a status string is available."""
        cleaned = (text or "").strip() or "Ready"
        idle = cleaned.casefold() in {
            "ready",
            "completed",
            "cancelled",
            "failed",
        }
        if idle:
            self._task.setText(cleaned if cleaned.casefold() != "ready" else "Ready")
            if cleaned.casefold() == "ready":
                self.reset()
                return
            self._progress_text.setText("—")
            self._bar.setValue(0)
            self._item.setText("—")
            self._elapsed.setText("—")
            self._eta.setText("—")
            return

        # Strip trailing progress fragments for the task title.
        task = cleaned
        for marker in (" (", " — ", "…"):
            if marker in task:
                task = task.split(marker, 1)[0].rstrip("…").strip()
                break
        self._task.setText(task or cleaned)

    def set_progress(
        self,
        *,
        task: str,
        current: int | None = None,
        total: int | None = None,
        item: str = "",
        elapsed_seconds: float = 0.0,
        eta_seconds: float | None = None,
        indeterminate: bool = False,
        percent: int | None = None,
        error: str = "",
    ) -> None:
        self._task.setText(task.strip() or "Working…")

        if percent is not None:
            pct = max(0, min(100, int(percent)))
            self._bar.setRange(0, 100)
            self._bar.setValue(pct)
            self._progress_text.setText(f"{pct}%")
        elif indeterminate or current is None or total is None or total <= 0:
            self._progress_text.setText("…")
            self._bar.setRange(0, 0)
        else:
            pct = int(round(100.0 * max(0, min(current, total)) / max(1, total)))
            self._bar.setRange(0, 100)
            self._bar.setValue(pct)
            self._progress_text.setText(f"{pct}%")
            if eta_seconds is None and current > 0 and elapsed_seconds > 0:
                remaining = total - current
                if remaining > 0:
                    eta_seconds = (elapsed_seconds / current) * remaining

        item_text = (error or item or "").strip() or "—"
        self._item.setText(item_text)
        self._elapsed.setText(_format_seconds(elapsed_seconds if elapsed_seconds > 0 else None))
        self._eta.setText(_format_seconds(eta_seconds))

    def set_from_generation_status(self, status) -> None:
        """Apply a GenerationStatus snapshot from the one-click queue."""
        self.set_progress(
            task=status.task,
            item=status.item,
            elapsed_seconds=status.elapsed_seconds,
            eta_seconds=status.eta_seconds,
            percent=status.progress_percent,
            error=status.error,
        )
