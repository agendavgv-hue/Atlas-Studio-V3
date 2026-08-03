"""Workflow progress banner — percent bar + stage checklist."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.projects.production_stages import StageState, WorkflowSnapshot
from app.ui.branding.status_icons import status_icon_pixmap


class WorkflowProgressPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProgressCard")

        self._percent = QLabel("0%")
        self._percent.setObjectName("WorkflowPercent")

        self._bar = QProgressBar()
        self._bar.setObjectName("WorkflowProgressBar")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(10)

        self._next = QLabel("Next: Generate Script")
        self._next.setObjectName("PageSubtitle")
        self._next.setWordWrap(True)

        self._checklist = QVBoxLayout()
        self._checklist.setSpacing(4)
        self._checklist.setContentsMargins(0, 0, 0, 0)

        head = QHBoxLayout()
        head.addWidget(QLabel("Production progress"))
        head.addStretch()
        head.addWidget(self._percent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        layout.addLayout(head)
        layout.addWidget(self._bar)
        layout.addWidget(self._next)
        layout.addLayout(self._checklist)

    def apply_snapshot(self, snapshot: WorkflowSnapshot) -> None:
        self._percent.setText(f"{snapshot.percent}%")
        self._bar.setValue(snapshot.percent)
        self._next.setText(f"Next: {snapshot.primary_action}")

        while self._checklist.count():
            item = self._checklist.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for stage in snapshot.stages:
            row = QWidget()
            row.setObjectName("ProgressRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 4, 4, 4)
            row_layout.setSpacing(10)
            icon = QLabel()
            icon.setPixmap(status_icon_pixmap(stage.state.icon_state, 16))
            icon.setFixedSize(20, 20)
            label = QLabel(stage.label)
            label.setObjectName("ProgressLabel")
            if stage.state is StageState.COMPLETED:
                label.setText(f"{stage.label}  ✓")
            row_layout.addWidget(icon)
            row_layout.addWidget(label, stretch=1)
            self._checklist.addWidget(row)
