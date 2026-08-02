"""Creative Director Training progress card."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout, QWidget

from app.channels.studio.training import TRAINING_SECTIONS, TrainingProgress


class TrainingCard(QFrame):
    """Shows how far the Creative Director has been trained."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusCard")

        title = QLabel("Creative Director Training")
        title.setObjectName("SectionLabel")
        self._subtitle = QLabel("Train each studio to teach your channel identity.")
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)

        self._percent = QLabel("0%")
        self._percent.setObjectName("PageTitle")
        self._percent.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(10)

        self._checklist = QLabel("")
        self._checklist.setObjectName("PageSubtitle")
        self._checklist.setWordWrap(True)

        self._badge = QLabel("")
        self._badge.setObjectName("SectionLabel")
        self._badge.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(self._subtitle)
        layout.addWidget(self._percent)
        layout.addWidget(self._bar)
        layout.addWidget(self._checklist)
        layout.addWidget(self._badge)

    def update_progress(self, progress: TrainingProgress) -> None:
        self._percent.setText(f"{progress.percent}%")
        self._bar.setValue(progress.percent)
        lines = []
        for key, label in TRAINING_SECTIONS:
            mark = "✓" if progress.completed.get(key) else "○"
            lines.append(f"{mark}  {label}")
        self._checklist.setText("\n".join(lines))
        self._subtitle.setText(
            f"{progress.done_count} of {progress.total} training areas complete."
        )
        if progress.fully_trained:
            self._badge.setText("Creative Director Fully Trained")
            self._badge.show()
        else:
            self._badge.hide()
