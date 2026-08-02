"""Design Review — layout candidates scored by the Design Engine."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.channels.models import Channel
from app.projects.project_paths import ProjectPaths
from app.projects.project_service import ProjectService
from app.thumbnail.design_engine.store import read_design_review
from app.thumbnail.naming import thumbnail_path


class DesignReviewPage(QWidget):
    """Visual debug of Design Engine layouts and the winning composition."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DesignReviewPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        title = QLabel("Design Review")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Atlas analyzes the illustration, tries dozens of layouts, and keeps the best design."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        pickers = QHBoxLayout()
        self._channel = QComboBox()
        self._project = QComboBox()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        pickers.addWidget(QLabel("Channel"))
        pickers.addWidget(self._channel, stretch=1)
        pickers.addWidget(QLabel("Project"))
        pickers.addWidget(self._project, stretch=1)
        pickers.addWidget(refresh)
        layout.addLayout(pickers)
        self._channel.currentIndexChanged.connect(self._on_channel_changed)
        self._project.currentIndexChanged.connect(self.reload)

        self._winner = QLabel("Winnaar: —")
        self._winner.setObjectName("SectionLabel")
        self._why = QLabel("")
        self._why.setObjectName("PageSubtitle")
        self._why.setWordWrap(True)
        layout.addWidget(self._winner)
        layout.addWidget(self._why)

        self._cards = QHBoxLayout()
        layout.addLayout(self._cards)

        scores_title = QLabel("Top layout scores")
        scores_title.setObjectName("SectionLabel")
        layout.addWidget(scores_title)
        self._score_grid = QGridLayout()
        layout.addLayout(self._score_grid)

        self._status = QLabel("Select a project with a Design Engine run.")
        self._status.setObjectName("PageSubtitle")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll)
        self._loading = False
        self.reload_channels()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reload_channels()

    def reload_channels(self) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        self._loading = True
        current = self._channel.currentData()
        self._channel.clear()
        for channel in app.channels.list_channels():
            name = channel.name if isinstance(channel, Channel) else str(channel)
            self._channel.addItem(name, name)
        if current:
            idx = self._channel.findData(current)
            if idx >= 0:
                self._channel.setCurrentIndex(idx)
        self._loading = False
        self._on_channel_changed()

    def _on_channel_changed(self) -> None:
        if self._loading:
            return
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        channel = self._channel.currentData()
        self._project.blockSignals(True)
        self._project.clear()
        if channel:
            for project in ProjectService(app.config).list_projects(str(channel)):
                self._project.addItem(project.name, project.folder_name)
        self._project.blockSignals(False)
        self.reload()

    def reload(self) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        channel = self._channel.currentData()
        folder = self._project.currentData()
        self._clear_cards()
        self._clear_scores()
        if not channel or not folder:
            self._winner.setText("Winnaar: —")
            self._why.setText("")
            self._status.setText("Select a channel and project.")
            return
        try:
            project_dir = ProjectPaths(app.config.project_root, str(channel)).project_dir(
                str(folder)
            )
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))
            return
        if not project_dir.is_dir():
            self._status.setText("Project folder not found.")
            return

        board = read_design_review(project_dir)
        if board is None:
            final = thumbnail_path(project_dir)
            self._winner.setText("Winnaar: — (no design_review.json yet)")
            self._why.setText("Generate a thumbnail to run the Design Engine.")
            if final.is_file():
                self._add_card("Final", None, final)
            self._status.setText("Waiting for Design Engine output.")
            return

        self._winner.setText(
            f"Winnaar: Layout {board.winner_id} · {board.winner_score:.0f}%"
        )
        self._why.setText(board.winner_why or "")
        for layout in board.layouts[:6]:
            path = project_dir / layout.image_relpath if layout.image_relpath else None
            if path is not None and not path.is_file():
                # try thumbnail-relative
                name = Path(layout.image_relpath).name
                path = project_dir / "thumbnail" / name
            winner = layout.id == board.winner_id
            label = f"Layout {layout.id}"
            if winner:
                label += " · WINNAAR"
            self._add_card(
                label,
                layout.scores.overall,
                path if path is not None and path.is_file() else None,
            )

        for i, layout in enumerate(board.layouts[:10]):
            key = QLabel(f"Layout {layout.id}")
            key.setObjectName("PageSubtitle")
            val = QLabel(f"{layout.scores.overall:.0f}%")
            val.setObjectName("SectionLabel")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._score_grid.addWidget(key, i, 0)
            self._score_grid.addWidget(val, i, 1)

        self._status.setText(
            f"{len(board.layouts)} layouts scored · winner {board.winner_id} "
            f"({board.winner_score:.0f}%)"
        )

    def _add_card(self, title: str, score: float | None, image_path: Path | None) -> None:
        card = QFrame()
        card.setObjectName("StatusCard")
        box = QVBoxLayout(card)
        head = QLabel(title)
        head.setObjectName("SectionLabel")
        score_label = QLabel("—" if score is None else f"{score:.0f}%")
        score_label.setObjectName("PageSubtitle")
        preview = QLabel("No preview")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumSize(200, 112)
        preview.setStyleSheet(
            "QLabel { background: rgba(0,0,0,0.22); border-radius: 6px; }"
        )
        if image_path is not None and image_path.is_file():
            pix = QPixmap(str(image_path))
            if not pix.isNull():
                preview.setPixmap(
                    pix.scaled(
                        200,
                        112,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        box.addWidget(head)
        box.addWidget(score_label)
        box.addWidget(preview)
        self._cards.addWidget(card)

    def _clear_cards(self) -> None:
        while self._cards.count():
            item = self._cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _clear_scores(self) -> None:
        while self._score_grid.count():
            item = self._score_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
