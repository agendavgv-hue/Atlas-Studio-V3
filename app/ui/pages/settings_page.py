"""Settings page — Project Root, AI text provider, Image provider, About."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.core.forge_settings import ForgeSettings
from app.providers.errors import ProviderError
from app.providers.forge import ForgeImageProvider
from app.providers.gemini import discover_text_models
from app.ui.dialogs.about_dialog import AboutDialog


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Settings")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Configure library location, AI text, and image providers.")
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

        model_label = QLabel("Gemini Model")
        model_label.setObjectName("PageSubtitle")

        self._model = QComboBox()
        self._model.setEditable(False)
        self._model.setPlaceholderText("Click Test Connection to load models")

        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self._test_gemini)

        save_ai_button = QPushButton("Save AI Settings")
        save_ai_button.setObjectName("PrimaryButton")
        save_ai_button.clicked.connect(self._save_ai)

        ai_actions = QHBoxLayout()
        ai_actions.addWidget(test_button)
        ai_actions.addWidget(save_ai_button)
        ai_actions.addStretch()

        image_label = QLabel("Image Provider")
        image_label.setObjectName("SectionLabel")

        self._image_provider = QComboBox()
        self._image_provider.addItem("Forge", "forge")

        self._forge_host = QLineEdit()
        self._forge_port = QLineEdit()
        self._forge_endpoint = QLineEdit()
        self._forge_model = QComboBox()
        self._forge_model.setEditable(True)
        self._forge_sampler = QLineEdit()
        self._forge_scheduler = QLineEdit()
        self._forge_steps = QLineEdit()
        self._forge_cfg = QLineEdit()
        self._forge_width = QLineEdit()
        self._forge_height = QLineEdit()
        self._forge_seed = QLineEdit()
        self._forge_negative = QLineEdit()

        forge_form = QFormLayout()
        forge_form.addRow("Host", self._forge_host)
        forge_form.addRow("Port", self._forge_port)
        forge_form.addRow("API Endpoint", self._forge_endpoint)
        forge_form.addRow("Model", self._forge_model)
        forge_form.addRow("Sampler", self._forge_sampler)
        forge_form.addRow("Scheduler", self._forge_scheduler)
        forge_form.addRow("Steps", self._forge_steps)
        forge_form.addRow("CFG Scale", self._forge_cfg)
        forge_form.addRow("Width", self._forge_width)
        forge_form.addRow("Height", self._forge_height)
        forge_form.addRow("Seed", self._forge_seed)
        forge_form.addRow("Negative Prompt", self._forge_negative)

        test_forge = QPushButton("Test Connection")
        test_forge.clicked.connect(self._test_forge)
        save_forge = QPushButton("Save Image Settings")
        save_forge.setObjectName("PrimaryButton")
        save_forge.clicked.connect(self._save_forge)
        forge_actions = QHBoxLayout()
        forge_actions.addWidget(test_forge)
        forge_actions.addWidget(save_forge)
        forge_actions.addStretch()

        about_button = QPushButton("About Atlas Studio")
        about_button.clicked.connect(self.open_about)

        self._status = QLabel("")
        self._status.setObjectName("PageSubtitle")
        self._status.setWordWrap(True)

        body = QWidget()
        layout = QVBoxLayout(body)
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
        layout.addWidget(model_label)
        layout.addWidget(self._model)
        layout.addLayout(ai_actions)
        layout.addSpacing(20)
        layout.addWidget(image_label)
        layout.addWidget(self._image_provider)
        layout.addLayout(forge_form)
        layout.addLayout(forge_actions)
        layout.addSpacing(24)
        layout.addWidget(about_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._status)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

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

        saved_model = (app.config.gemini_model or "").strip()
        self._set_combo_models(self._model, [saved_model] if saved_model else [], preferred=saved_model)

        image_provider = app.config.image_provider or "forge"
        img_index = self._image_provider.findData(image_provider)
        if img_index >= 0:
            self._image_provider.setCurrentIndex(img_index)

        forge = app.config.forge
        self._forge_host.setText(forge.host)
        self._forge_port.setText(str(forge.port))
        self._forge_endpoint.setText(forge.endpoint)
        self._set_combo_models(
            self._forge_model,
            [forge.model] if forge.model else [],
            preferred=forge.model,
        )
        self._forge_sampler.setText(forge.sampler)
        self._forge_scheduler.setText(forge.scheduler)
        self._forge_steps.setText(str(forge.steps))
        self._forge_cfg.setText(str(forge.cfg_scale))
        self._forge_width.setText(str(forge.width))
        self._forge_height.setText(str(forge.height))
        self._forge_seed.setText(str(forge.seed))
        self._forge_negative.setText(forge.negative_prompt)

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

    def _test_gemini(self) -> None:
        key = self._api_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Atlas Studio", "Enter a Gemini API key first.")
            return

        self._status.setText("Testing Gemini connection…")
        app = self._app()
        if app is not None:
            app.processEvents()

        try:
            models = discover_text_models(key)
        except ProviderError as exc:
            self._status.setText(str(exc))
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return

        preferred = self._model.currentText().strip()
        self._set_combo_models(self._model, models, preferred=preferred)
        selected = self._model.currentText().strip()
        self._status.setText(
            f"Gemini OK — {len(models)} model(s). Selected: {selected}"
        )
        if app is not None:
            app.show_notification("Gemini Connected", f"{len(models)} models found")

    def _save_ai(self) -> None:
        app = self._app()
        if app is None:
            return
        key = self._api_key.text().strip()
        model = self._model.currentText().strip()
        if not key:
            QMessageBox.warning(self, "Atlas Studio", "Enter a Gemini API key.")
            return
        if not model:
            QMessageBox.warning(
                self,
                "Atlas Studio",
                "No model selected. Click Test Connection to load available models.",
            )
            return

        app.config.text_provider = str(self._provider.currentData() or "gemini")
        app.config.gemini_api_key = key
        app.config.gemini_model = model
        app.config.save()
        app.rebuild_production_engine()
        self._status.setText(f"AI settings saved ({model}).")
        app.show_notification("AI Settings Saved", model)

    def _read_forge_settings(self) -> ForgeSettings:
        return ForgeSettings.from_mapping(
            {
                "host": self._forge_host.text(),
                "port": self._forge_port.text(),
                "endpoint": self._forge_endpoint.text(),
                "model": self._forge_model.currentText(),
                "sampler": self._forge_sampler.text(),
                "scheduler": self._forge_scheduler.text(),
                "steps": self._forge_steps.text(),
                "cfg_scale": self._forge_cfg.text(),
                "width": self._forge_width.text(),
                "height": self._forge_height.text(),
                "seed": self._forge_seed.text(),
                "negative_prompt": self._forge_negative.text(),
            }
        )

    def _test_forge(self) -> None:
        settings = self._read_forge_settings()
        self._status.setText("Testing Forge connection…")
        app = self._app()
        if app is not None:
            app.processEvents()
        provider = ForgeImageProvider(settings)
        try:
            message = provider.test_connection()
            models = provider.list_models()
        except ProviderError as exc:
            self._status.setText(str(exc))
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        preferred = self._forge_model.currentText().strip()
        self._set_combo_models(self._forge_model, models, preferred=preferred)
        self._status.setText(message)
        if app is not None:
            app.show_notification("Forge Connected", message)

    def _save_forge(self) -> None:
        app = self._app()
        if app is None:
            return
        settings = self._read_forge_settings()
        if settings.width <= 0 or settings.height <= 0:
            QMessageBox.warning(self, "Atlas Studio", "Width and height must be positive.")
            return
        app.config.image_provider = str(self._image_provider.currentData() or "forge")
        app.config.forge = settings
        app.config.save()
        app.rebuild_production_engine()
        self._status.setText(
            f"Image settings saved ({settings.host}:{settings.port}, {settings.width}×{settings.height})."
        )
        app.show_notification("Image Settings Saved", settings.model or "Forge")

    @staticmethod
    def _set_combo_models(combo: QComboBox, models: list[str], *, preferred: str = "") -> None:
        combo.blockSignals(True)
        combo.clear()
        for model_id in models:
            if model_id:
                combo.addItem(model_id)
        if preferred and combo.findText(preferred) >= 0:
            combo.setCurrentText(preferred)
        elif preferred:
            combo.addItem(preferred)
            combo.setCurrentText(preferred)
        elif combo.count() > 0:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
