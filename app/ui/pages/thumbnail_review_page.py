"""Thumbnail Review — critic versions, scores, and winner."""

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
from app.thumbnail.critic_engine.store import read_review_board
from app.thumbnail.naming import resolve_thumbnail_dir, thumbnail_path


class ThumbnailReviewPage(QWidget):
    """Visual debug of critic iterations and the winning thumbnail."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ThumbnailReviewPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        title = QLabel("Thumbnail Review")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Critic iterations, scores, and the winning thumbnail — Atlas keeps improving until it looks professional."
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
        layout.addWidget(self._winner)

        self._versions = QHBoxLayout()
        self._version_cards: list[QFrame] = []
        layout.addLayout(self._versions)

        scores_title = QLabel("Score overview")
        scores_title.setObjectName("SectionLabel")
        layout.addWidget(scores_title)
        self._score_grid = QGridLayout()
        layout.addLayout(self._score_grid)

        self._status = QLabel("Select a project with a generated thumbnail.")
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
            projects = ProjectService(app.config).list_projects(str(channel))
            for project in projects:
                self._project.addItem(project.name, project.folder_name)
        self._project.blockSignals(False)
        self.reload()

    def reload(self) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            return
        channel = self._channel.currentData()
        folder = self._project.currentData()
        self._clear_versions()
        self._clear_scores()
        if not channel or not folder:
            self._winner.setText("Winnaar: —")
            self._status.setText("Select a channel and project.")
            return
        try:
            paths = ProjectPaths(app.config.project_root, str(channel))
            project_dir = paths.project_dir(str(folder))
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))
            return
        if not project_dir.is_dir():
            self._status.setText("Project folder not found.")
            return
        board = read_review_board(project_dir)
        if board is None:
            # Fallback: show final thumbnail only
            final = thumbnail_path(project_dir)
            self._winner.setText("Winnaar: final thumbnail (no review board yet)")
            if final.is_file():
                self._add_version_card("Final", None, final)
            self._status.setText(
                "Generate a thumbnail to create thumbnail_review.json with critic iterations."
            )
            return

        self._winner.setText(
            f"Winnaar: Thumbnail {board.winner_attempt} · Score {board.winner_score:.0f}"
        )
        for version in board.versions:
            path = project_dir / version.image_relpath.replace("\\", "/").split("/", 1)[-1]
            if not path.is_file():
                # image_relpath is thumbnail/thumbnail_attempt_N.png
                path = project_dir / version.image_relpath
            if not path.is_file():
                path = resolve_thumbnail_dir(project_dir) / f"thumbnail_attempt_{version.attempt}.png"
            winner = version.attempt == board.winner_attempt
            label = f"Thumbnail {version.attempt}"
            if winner:
                label += " · WINNAAR"
            self._add_version_card(label, version.overall, path if path.is_file() else None)

        groups = board.groups.to_dict()
        rows = [
            ("Storytelling", groups.get("Story")),
            ("Brand Match", groups.get("Brand")),
            ("Layout", groups.get("Layout")),
            ("Composition", groups.get("Composition")),
            ("Curiosity", groups.get("Curiosity")),
            ("CTR Potential", groups.get("CTR")),
            ("Overall", groups.get("Overall")),
        ]
        for i, (name, value) in enumerate(rows):
            key = QLabel(name)
            key.setObjectName("PageSubtitle")
            val = QLabel("—" if value is None else f"{float(value):.0f}")
            val.setObjectName("SectionLabel")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._score_grid.addWidget(key, i, 0)
            self._score_grid.addWidget(val, i, 1)

        self._status.setText(
            f"Loaded critic review for {board.channel_name} · "
            f"{len(board.versions)} version(s) · threshold {board.threshold}"
        )

    def _add_version_card(self, title: str, score: float | None, image_path: Path | None) -> None:
        card = QFrame()
        card.setObjectName("StatusCard")
        box = QVBoxLayout(card)
        head = QLabel(title)
        head.setObjectName("SectionLabel")
        score_label = QLabel("—" if score is None else f"Score {score:.0f}")
        score_label.setObjectName("PageSubtitle")
        preview = QLabel("No preview")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumSize(220, 124)
        preview.setStyleSheet("QLabel { background: rgba(0,0,0,0.22); border-radius: 6px; }")
        if image_path is not None and image_path.is_file():
            pix = QPixmap(str(image_path))
            if not pix.isNull():
                preview.setPixmap(
                    pix.scaled(
                        220,
                        124,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        box.addWidget(head)
        box.addWidget(score_label)
        box.addWidget(preview)
        self._versions.addWidget(card)
        self._version_cards.append(card)

    def _clear_versions(self) -> None:
        while self._versions.count():
            item = self._versions.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._version_cards.clear()

    def _clear_scores(self) -> None:
        while self._score_grid.count():
            item = self._score_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
