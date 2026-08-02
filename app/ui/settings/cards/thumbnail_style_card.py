"""Thumbnail Style settings card — manage reference thumbnails + DNA analysis."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.services.thumbnail_dna_service import MAX_REFERENCES
from app.services.thumbnail_reference_service import ThumbnailReferenceService


class ThumbnailStyleCard(QWidget):
    """Settings card: upload ≤10 refs, preview, analyze → Thumbnail DNA."""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channel: str = ""

        title = QLabel("Thumbnail Style")
        title.setObjectName("SectionLabel")

        self._hint = QLabel(
            "Upload up to 10 reference thumbnails for the active channel. "
            "Atlas learns STYLE only (layout, colors, lighting, emotion) — "
            "not video content. Analysis writes thumbnail_dna.json used by "
            "every new thumbnail."
        )
        self._hint.setObjectName("PageSubtitle")
        self._hint.setWordWrap(True)

        self._channel_label = QLabel("Active channel: —")
        self._channel_label.setObjectName("PageSubtitle")

        self._count_label = QLabel("0 / 10 references")
        self._count_label.setObjectName("PageSubtitle")

        self._list = QListWidget()
        self._list.setMinimumHeight(140)
        self._list.currentItemChanged.connect(self._on_selection)

        self._preview = QLabel("Select a reference to preview")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(160)
        self._preview.setStyleSheet(
            "QLabel { background: rgba(0,0,0,0.25); border-radius: 6px; }"
        )
        self._preview.setScaledContents(False)

        add_btn = QPushButton("Add References…")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_references)

        replace_btn = QPushButton("Replace")
        replace_btn.clicked.connect(self._replace_reference)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_reference)

        analyze_btn = QPushButton("Analyse References")
        analyze_btn.setObjectName("PrimaryButton")
        analyze_btn.clicked.connect(self._analyze)

        actions = QHBoxLayout()
        actions.addWidget(add_btn)
        actions.addWidget(replace_btn)
        actions.addWidget(delete_btn)
        actions.addWidget(analyze_btn)
        actions.addStretch()

        self._dna_status = QLabel("")
        self._dna_status.setObjectName("PageSubtitle")
        self._dna_status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(self._hint)
        layout.addWidget(self._channel_label)
        layout.addWidget(self._count_label)
        layout.addWidget(self._list)
        layout.addWidget(self._preview)
        layout.addLayout(actions)
        layout.addWidget(self._dna_status)

    def refresh(self) -> None:
        app = self._app()
        if app is None:
            self._channel = ""
            self._channel_label.setText("Active channel: —")
            self._list.clear()
            self._count_label.setText("0 / 10 references")
            self._dna_status.setText("Application is not ready.")
            return

        channel = app.channels.active_channel_name or ""
        if not channel:
            channels = app.channels.list_channels()
            channel = channels[0].folder_name if channels else ""
        self._channel = channel
        self._channel_label.setText(
            f"Active channel: {channel}" if channel else "Active channel: —"
        )

        if not channel:
            self._list.clear()
            self._count_label.setText("0 / 10 references")
            self._dna_status.setText("Select a channel on the Channels page first.")
            return

        service = self._service(app)
        refs = service.load_references(channel)
        self._list.clear()
        for path in refs:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self._list.addItem(item)
        self._count_label.setText(f"{len(refs)} / {MAX_REFERENCES} references")

        dna = service.get_thumbnail_dna(channel)
        if dna is None:
            stale = " — analysis needed" if refs else ""
            self._dna_status.setText(f"Thumbnail DNA: not built yet{stale}")
        elif service.is_dna_stale(channel):
            self._dna_status.setText(
                f"Thumbnail DNA: stale ({dna.reference_count} refs analyzed) — re-analyse"
            )
        else:
            self._dna_status.setText(
                f"Thumbnail DNA ready · emotion {dna.style.emotion} · "
                f"lighting {dna.style.lighting} · "
                f"title {dna.layout.title_position}"
            )

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _service(self, app: AtlasApplication) -> ThumbnailReferenceService:
        text = None
        try:
            text = app.production.resolve_text_provider()
        except Exception:  # noqa: BLE001
            text = None
        return ThumbnailReferenceService(app.config.data_root, text_provider=text)

    def _selected_path(self) -> Path | None:
        item = self._list.currentItem()
        if item is None:
            return None
        raw = item.data(Qt.ItemDataRole.UserRole)
        return Path(str(raw)) if raw else None

    def _on_selection(self, current: QListWidgetItem | None, _previous) -> None:
        if current is None:
            self._preview.setText("Select a reference to preview")
            self._preview.setPixmap(QPixmap())
            return
        path = Path(str(current.data(Qt.ItemDataRole.UserRole) or ""))
        if not path.is_file():
            return
        pix = QPixmap(str(path))
        if pix.isNull():
            self._preview.setText("Could not load preview")
            return
        scaled = pix.scaled(
            self._preview.width() or 320,
            self._preview.height() or 160,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    def _add_references(self) -> None:
        app = self._app()
        if app is None or not self._channel:
            QMessageBox.warning(self, "Thumbnail Style", "Select a channel first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select reference thumbnails",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)",
        )
        if not paths:
            return
        service = self._service(app)
        added = 0
        for raw in paths:
            try:
                service.save_reference(self._channel, Path(raw))
                added += 1
            except ValueError as exc:
                QMessageBox.warning(self, "Thumbnail Style", str(exc))
                break
            except OSError as exc:
                QMessageBox.warning(self, "Thumbnail Style", str(exc))
                break
        self.refresh()
        if added:
            self.status_message.emit(f"Added {added} reference(s)")

    def _replace_reference(self) -> None:
        app = self._app()
        target = self._selected_path()
        if app is None or not self._channel or target is None:
            QMessageBox.warning(self, "Thumbnail Style", "Select a reference to replace.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Replace reference thumbnail",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)",
        )
        if not path:
            return
        try:
            self._service(app).replace_reference(self._channel, target, Path(path))
        except (OSError, ValueError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Thumbnail Style", str(exc))
            return
        self.refresh()
        self.status_message.emit("Reference replaced")

    def _delete_reference(self) -> None:
        app = self._app()
        target = self._selected_path()
        if app is None or not self._channel or target is None:
            QMessageBox.warning(self, "Thumbnail Style", "Select a reference to delete.")
            return
        try:
            self._service(app).delete_reference(self._channel, target)
        except (OSError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Thumbnail Style", str(exc))
            return
        self.refresh()
        self.status_message.emit("Reference deleted")

    def _analyze(self) -> None:
        app = self._app()
        if app is None or not self._channel:
            QMessageBox.warning(self, "Thumbnail Style", "Select a channel first.")
            return
        service = self._service(app)
        try:
            dna = service.analyze(self._channel)
        except ValueError as exc:
            QMessageBox.warning(self, "Thumbnail Style", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Thumbnail Style", f"Analysis failed: {exc}")
            return
        self.refresh()
        mode = (dna.extras or {}).get("analysis_mode", "ai")
        self.status_message.emit(
            f"Thumbnail DNA saved ({dna.reference_count} refs, {mode})"
        )
        app.show_notification(
            "Thumbnail DNA Ready",
            f"{self._channel} · {dna.style.emotion} · {dna.style.lighting}",
        )
