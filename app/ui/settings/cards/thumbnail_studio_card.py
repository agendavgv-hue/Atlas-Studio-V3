"""Thumbnail Studio settings card — intelligence knobs + reference library."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.services.thumbnail_dna_service import MAX_REFERENCES
from app.thumbnail.intelligence.service import ThumbnailIntelligenceService
from app.thumbnail.intelligence.settings import LOGO_POSITIONS, ThumbnailStudioSettings


class ThumbnailStudioCard(QWidget):
    """Per-channel Thumbnail Intelligence Studio."""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channel = ""

        title = QLabel("Thumbnail Studio")
        title.setObjectName("SectionLabel")
        hint = QLabel(
            "Design thumbnails from Creative Director, Brand Kit, Style Library, "
            "Reference Library, and Thumbnail DNA — never freeform style guesses."
        )
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)

        self._channel_label = QLabel("Active channel: —")
        self._channel_label.setObjectName("PageSubtitle")

        self._style = QComboBox()
        for item in ("cinematic", "documentary", "mystery", "dramatic", "clean"):
            self._style.addItem(item.title(), item)
        self._quality = QComboBox()
        for item in ("ultra", "high", "standard"):
            self._quality.addItem(item.title(), item)
        self._creativity = QDoubleSpinBox()
        self._creativity.setRange(0, 100)
        self._creativity.setDecimals(0)
        self._style_strength = QDoubleSpinBox()
        self._style_strength.setRange(0, 100)
        self._style_strength.setDecimals(0)
        self._brand_strength = QDoubleSpinBox()
        self._brand_strength.setRange(0, 100)
        self._brand_strength.setDecimals(0)
        self._logo_visible = QCheckBox("Logo visible")
        self._logo_position = QComboBox()
        for pos in LOGO_POSITIONS:
            self._logo_position.addItem(pos.replace("_", " ").title(), pos)
        self._max_words = QSpinBox()
        self._max_words.setRange(1, 8)
        self._negative_space = QComboBox()
        for side in ("left", "right", "top", "bottom"):
            self._negative_space.addItem(side.title(), side)
        self._contrast = QComboBox()
        for item in ("very_high", "high", "medium"):
            self._contrast.addItem(item.replace("_", " ").title(), item)

        form = QFormLayout()
        form.addRow("Thumbnail Style", self._style)
        form.addRow("Quality", self._quality)
        form.addRow("Creativity", self._creativity)
        form.addRow("Style Strength", self._style_strength)
        form.addRow("Brand Strength", self._brand_strength)
        form.addRow("Logo", self._logo_visible)
        form.addRow("Logo Position", self._logo_position)
        form.addRow("Maximum Words", self._max_words)
        form.addRow("Negative Space", self._negative_space)
        form.addRow("Contrast", self._contrast)

        save_btn = QPushButton("Save Thumbnail Studio")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._save_settings)

        refs_label = QLabel("Reference Library (max 10)")
        refs_label.setObjectName("SectionLabel")
        self._count_label = QLabel("0 / 10 references")
        self._count_label.setObjectName("PageSubtitle")
        self._list = QListWidget()
        self._list.setMinimumHeight(120)
        self._list.currentItemChanged.connect(self._on_selection)
        self._preview = QLabel("Select a reference to preview")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(140)
        self._preview.setStyleSheet(
            "QLabel { background: rgba(0,0,0,0.25); border-radius: 6px; }"
        )

        add_btn = QPushButton("Upload…")
        add_btn.clicked.connect(self._add_references)
        replace_btn = QPushButton("Replace")
        replace_btn.clicked.connect(self._replace_reference)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_reference)
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self._open_reference)
        analyze_btn = QPushButton("Analyse References")
        analyze_btn.setObjectName("PrimaryButton")
        analyze_btn.clicked.connect(self._analyze)

        ref_actions = QHBoxLayout()
        ref_actions.addWidget(add_btn)
        ref_actions.addWidget(replace_btn)
        ref_actions.addWidget(delete_btn)
        ref_actions.addWidget(open_btn)
        ref_actions.addWidget(analyze_btn)
        ref_actions.addStretch()

        self._dna_status = QLabel("")
        self._dna_status.setObjectName("PageSubtitle")
        self._dna_status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self._channel_label)
        layout.addLayout(form)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(12)
        layout.addWidget(refs_label)
        layout.addWidget(self._count_label)
        layout.addWidget(self._list)
        layout.addWidget(self._preview)
        layout.addLayout(ref_actions)
        layout.addWidget(self._dna_status)

    def refresh(self) -> None:
        app = self._app()
        if app is None:
            self._channel = ""
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
            return

        intel = self._intel(app)
        settings = intel.load_settings(channel)
        self._set_combo(self._style, settings.thumbnail_style)
        self._set_combo(self._quality, settings.quality)
        self._creativity.setValue(settings.creativity)
        self._style_strength.setValue(settings.style_strength)
        self._brand_strength.setValue(settings.brand_strength)
        self._logo_visible.setChecked(settings.logo_visible)
        self._set_combo(self._logo_position, settings.logo_position)
        self._max_words.setValue(settings.max_words)
        self._set_combo(self._negative_space, settings.negative_space)
        self._set_combo(self._contrast, settings.contrast)

        refs = intel.references(channel).load_references(channel)
        self._list.clear()
        for path in refs:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self._list.addItem(item)
        self._count_label.setText(f"{len(refs)} / {MAX_REFERENCES} references")

        service = intel.references(channel)
        dna = service.get_thumbnail_dna(channel)
        if dna is None:
            self._dna_status.setText(
                "Thumbnail DNA: not built yet" + (" — analyse needed" if refs else "")
            )
        elif service.is_dna_stale(channel):
            self._dna_status.setText("Thumbnail DNA: stale — re-analyse references")
        else:
            self._dna_status.setText(
                f"Thumbnail DNA ready · {dna.style.emotion} · "
                f"{dna.style.lighting} · title {dna.layout.title_position}"
            )

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _intel(self, app: AtlasApplication) -> ThumbnailIntelligenceService:
        text = None
        try:
            text = app.production.resolve_text_provider()
        except Exception:  # noqa: BLE001
            text = None
        return ThumbnailIntelligenceService(app.config.data_root, text_provider=text)

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findData(value.casefold())
        if index >= 0:
            combo.setCurrentIndex(index)

    def _read_settings(self) -> ThumbnailStudioSettings:
        return ThumbnailStudioSettings(
            thumbnail_style=str(self._style.currentData() or "cinematic"),
            quality=str(self._quality.currentData() or "ultra"),
            creativity=float(self._creativity.value()),
            style_strength=float(self._style_strength.value()),
            brand_strength=float(self._brand_strength.value()),
            logo_visible=self._logo_visible.isChecked(),
            logo_position=str(self._logo_position.currentData() or "auto"),
            max_words=int(self._max_words.value()),
            negative_space=str(self._negative_space.currentData() or "left"),
            contrast=str(self._contrast.currentData() or "very_high"),
        )

    def _save_settings(self) -> None:
        app = self._app()
        if app is None or not self._channel:
            QMessageBox.warning(self, "Thumbnail Studio", "Select a channel first.")
            return
        self._intel(app).save_settings(self._channel, self._read_settings())
        self.status_message.emit("Thumbnail Studio settings saved")
        app.show_notification("Thumbnail Studio", f"Saved for {self._channel}")

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
        pix = QPixmap(str(path))
        if pix.isNull():
            self._preview.setText("Could not load preview")
            return
        scaled = pix.scaled(
            self._preview.width() or 320,
            self._preview.height() or 140,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    def _add_references(self) -> None:
        app = self._app()
        if app is None or not self._channel:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Upload thumbnail references",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)",
        )
        if not paths:
            return
        service = self._intel(app).references(self._channel)
        added = 0
        for raw in paths:
            try:
                service.save_reference(self._channel, Path(raw))
                added += 1
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Thumbnail Studio", str(exc))
                break
        self.refresh()
        if added:
            self.status_message.emit(f"Added {added} reference(s)")

    def _replace_reference(self) -> None:
        app = self._app()
        target = self._selected_path()
        if app is None or not self._channel or target is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Replace reference",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)",
        )
        if not path:
            return
        try:
            self._intel(app).references(self._channel).replace_reference(
                self._channel, target, Path(path)
            )
        except (OSError, ValueError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Thumbnail Studio", str(exc))
            return
        self.refresh()

    def _delete_reference(self) -> None:
        app = self._app()
        target = self._selected_path()
        if app is None or not self._channel or target is None:
            return
        try:
            self._intel(app).references(self._channel).delete_reference(
                self._channel, target
            )
        except (OSError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Thumbnail Studio", str(exc))
            return
        self.refresh()

    def _open_reference(self) -> None:
        target = self._selected_path()
        if target is None or not target.is_file():
            return
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _analyze(self) -> None:
        app = self._app()
        if app is None or not self._channel:
            return
        try:
            dna = self._intel(app).references(self._channel).analyze(self._channel)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Thumbnail Studio", str(exc))
            return
        self.refresh()
        self.status_message.emit(f"Thumbnail DNA saved ({dna.reference_count} refs)")
        app.show_notification(
            "Thumbnail DNA Ready",
            f"{self._channel} · {dna.style.emotion} · {dna.style.lighting}",
        )
