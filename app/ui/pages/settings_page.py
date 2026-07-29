"""Settings page — Project Root, AI provider, and About."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.ui.dialogs.about_dialog import AboutDialog


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Settings")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Configure library location and AI text provider.")
        subtitle.setObjectName("PageSubtitle")

        root_label = QLabel("Project Root")
        root_label.setObjectName("SectionLabel")

        self._root_input = QLineEdit()
        self._root_input.setPlaceholderText(r"e.g. D:\OneDrive\YouTube")

        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse)

        save_root_button = QPushButton("Save Project Root")
        save_root_button.setObjectName("PrimaryButton")
        save_root_button.clicked.connect(self._save_root)

        root_row = QHBoxLayout()
        root_row.addWidget(self._root_input, stretch=1)
        root_row.addWidget(browse_button)

        ai_label = QLabel("AI Text Provider")
        ai_label.setObjectName("SectionLabel")

        self._provider = QComboBox()
        self._provider.addItem("Gemini", "gemini")

        key_label = QLabel("Gemini API Key")
        key_label.setObjectName("PageSubtitle")

        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setPlaceholderText("Paste API key")

        save_ai_button = QPushButton("Save AI Settings")
        save_ai_button.setObjectName("PrimaryButton")
        save_ai_button.clicked.connect(self._save_ai)

        about_button = QPushButton("About Atlas Studio")
        about_button.clicked.connect(self.open_about)

        self._status = QLabel("")
        self._status.setObjectName("PageSubtitle")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(root_label)
        layout.addLayout(root_row)
        layout.addWidget(save_root_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(20)
        layout.addWidget(ai_label)
        layout.addWidget(self._provider)
        layout.addWidget(key_label)
        layout.addWidget(self._api_key)
        layout.addWidget(save_ai_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(24)
        layout.addWidget(about_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._status)
        layout.addStretch()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._load_current()

    def open_about(self) -> None:
        AboutDialog(self).exec()

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _load_current(self) -> None:
        app = self._app()
        if app is None:
            return
        current = app.config.project_root
        self._root_input.setText(str(current) if current else "")
        self._api_key.setText(app.config.gemini_api_key or "")
        provider = app.config.text_provider or "gemini"
        index = self._provider.findData(provider)
        if index >= 0:
            self._provider.setCurrentIndex(index)
        if current:
            self._status.setText(f"Current Project Root: {current}")
        else:
            self._status.setText("No Project Root configured yet.")

    def _browse(self) -> None:
        start = self._root_input.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select Project Root", start)
        if chosen:
            self._root_input.setText(chosen)

    def _save_root(self) -> None:
        app = self._app()
        if app is None:
            return
        text = self._root_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Atlas Studio", "Choose a Project Root folder.")
            return
        try:
            resolved = app.channels.set_project_root(Path(text))
        except OSError as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._root_input.setText(str(resolved))
        self._status.setText(f"Saved Project Root: {resolved}")
        app.show_notification("Project Root Saved", str(resolved))

    def _save_ai(self) -> None:
        app = self._app()
        if app is None:
            return
        app.config.text_provider = str(self._provider.currentData() or "gemini")
        app.config.gemini_api_key = self._api_key.text().strip()
        app.config.save()
        app.rebuild_production_engine()
        self._status.setText("AI settings saved.")
        app.show_notification("AI Settings Saved", app.config.text_provider or "gemini")
