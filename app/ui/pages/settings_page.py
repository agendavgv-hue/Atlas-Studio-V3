"""Settings page — Project Root, AI text, Image, Voice providers, About."""

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
from app.core.movie_settings import (
    MOTION_STYLES,
    RENDER_PROFILES,
    TRANSITION_STYLES,
    MovieSettings,
)
from app.core.voice_settings import VoiceSettings
from app.providers.elevenlabs import ElevenLabsVoiceProvider
from app.providers.errors import ProviderError
from app.providers.forge import ForgeImageProvider
from app.providers.gemini import discover_text_models
from app.providers.local_voice import (
    LOCAL_VOICE_PROVIDER_ID,
    LOCAL_VOICE_PROVIDER_LABEL,
    LocalVoiceProvider,
)
from app.render.ffmpeg import FFmpegProcess
from app.ui.dialogs.about_dialog import AboutDialog


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Settings")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Configure library location, AI text, image, voice, and movie providers."
        )
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

        voice_label = QLabel("Voice Provider")
        voice_label.setObjectName("SectionLabel")

        self._voice_provider = QComboBox()
        self._voice_provider.addItem(LOCAL_VOICE_PROVIDER_LABEL, LOCAL_VOICE_PROVIDER_ID)
        self._voice_provider.addItem("ElevenLabs (Optional)", "elevenlabs")
        # Future optional cloud plugins: OpenAI, Azure, Google, …
        self._voice_provider.currentIndexChanged.connect(self._sync_voice_provider_fields)

        self._voice_api_key = QLineEdit()
        self._voice_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._voice_api_key.setPlaceholderText("Required for cloud providers only")

        self._voice_voice = QComboBox()
        self._voice_voice.setEditable(True)
        self._voice_voice.setPlaceholderText("Click Test Connection to load voices")

        self._voice_language = QLineEdit()
        self._voice_language.setPlaceholderText("e.g. en-US")
        self._voice_model = QComboBox()
        self._voice_model.setEditable(True)
        self._voice_stability = QLineEdit()
        self._voice_style = QLineEdit()
        self._voice_speed = QLineEdit()
        self._voice_similarity = QLineEdit()
        self._voice_output_format = QLineEdit()
        self._voice_output_format.setPlaceholderText("mp3 or wav")

        self._voice_hint = QLabel(
            "Local Voice Engine works offline and requires no subscription. "
            "Cloud providers are optional."
        )
        self._voice_hint.setObjectName("PageSubtitle")
        self._voice_hint.setWordWrap(True)

        voice_form = QFormLayout()
        self._voice_api_key_label = QLabel("API Key")
        voice_form.addRow(self._voice_api_key_label, self._voice_api_key)
        voice_form.addRow("Voice", self._voice_voice)
        voice_form.addRow("Language", self._voice_language)
        self._voice_model_label = QLabel("Model")
        voice_form.addRow(self._voice_model_label, self._voice_model)
        self._voice_stability_label = QLabel("Stability")
        voice_form.addRow(self._voice_stability_label, self._voice_stability)
        self._voice_style_label = QLabel("Style")
        voice_form.addRow(self._voice_style_label, self._voice_style)
        voice_form.addRow("Speed", self._voice_speed)
        self._voice_similarity_label = QLabel("Similarity")
        voice_form.addRow(self._voice_similarity_label, self._voice_similarity)
        voice_form.addRow("Output Format", self._voice_output_format)

        test_voice = QPushButton("Test Connection")
        test_voice.clicked.connect(self._test_voice)
        save_voice = QPushButton("Save Voice Settings")
        save_voice.setObjectName("PrimaryButton")
        save_voice.clicked.connect(self._save_voice)
        voice_actions = QHBoxLayout()
        voice_actions.addWidget(test_voice)
        voice_actions.addWidget(save_voice)
        voice_actions.addStretch()

        movie_label = QLabel("Movie Settings")
        movie_label.setObjectName("SectionLabel")

        self._movie_ffmpeg = QLineEdit()
        self._movie_ffmpeg.setPlaceholderText("Auto-detect from PATH if empty")
        self._movie_profile = QComboBox()
        for profile_id, spec in RENDER_PROFILES.items():
            self._movie_profile.addItem(spec.label, profile_id)
        self._movie_transition = QComboBox()
        for item in TRANSITION_STYLES:
            self._movie_transition.addItem(item.replace("_", " ").title(), item)
        self._movie_motion = QComboBox()
        for item in MOTION_STYLES:
            self._movie_motion.addItem(item.replace("_", " ").title(), item)
        self._movie_duration = QLineEdit()
        self._movie_width = QLineEdit()
        self._movie_height = QLineEdit()
        self._movie_fps = QLineEdit()
        self._movie_codec = QLineEdit()
        self._movie_preset = QLineEdit()
        self._movie_crf = QLineEdit()
        self._movie_keep_scenes = QComboBox()
        self._movie_keep_scenes.addItem("No (default)", False)
        self._movie_keep_scenes.addItem("Yes — keep scene renders in mp4/", True)

        movie_form = QFormLayout()
        movie_form.addRow("FFmpeg Path", self._movie_ffmpeg)
        movie_form.addRow("Render Profile", self._movie_profile)
        movie_form.addRow("Transition", self._movie_transition)
        movie_form.addRow("Scene Animation", self._movie_motion)
        movie_form.addRow("Default Duration (sec/image)", self._movie_duration)
        movie_form.addRow("Custom Width", self._movie_width)
        movie_form.addRow("Custom Height", self._movie_height)
        movie_form.addRow("FPS", self._movie_fps)
        movie_form.addRow("Codec", self._movie_codec)
        movie_form.addRow("Quality Preset", self._movie_preset)
        movie_form.addRow("CRF", self._movie_crf)
        movie_form.addRow("Keep Scene Renders", self._movie_keep_scenes)

        test_movie = QPushButton("Test FFmpeg")
        test_movie.clicked.connect(self._test_ffmpeg)
        save_movie = QPushButton("Save Movie Settings")
        save_movie.setObjectName("PrimaryButton")
        save_movie.clicked.connect(self._save_movie)
        movie_actions = QHBoxLayout()
        movie_actions.addWidget(test_movie)
        movie_actions.addWidget(save_movie)
        movie_actions.addStretch()

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
        layout.addSpacing(20)
        layout.addWidget(voice_label)
        layout.addWidget(self._voice_provider)
        layout.addWidget(self._voice_hint)
        layout.addLayout(voice_form)
        layout.addLayout(voice_actions)
        layout.addSpacing(20)
        layout.addWidget(movie_label)
        layout.addLayout(movie_form)
        layout.addLayout(movie_actions)
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

        voice_provider = app.config.voice_provider or LOCAL_VOICE_PROVIDER_ID
        if voice_provider.casefold() == "kokoro":
            voice_provider = LOCAL_VOICE_PROVIDER_ID
        voice_index = self._voice_provider.findData(voice_provider)
        if voice_index >= 0:
            self._voice_provider.setCurrentIndex(voice_index)

        voice = app.config.voice
        self._voice_api_key.setText(voice.api_key)
        self._set_voice_combo(voice.voice_id, voice.voice_name)
        self._voice_language.setText(voice.language or "en-US")
        self._set_combo_models(
            self._voice_model,
            [voice.model] if voice.model else [],
            preferred=voice.model,
        )
        self._voice_stability.setText(str(voice.stability))
        self._voice_style.setText(str(voice.style))
        self._voice_speed.setText(str(voice.speed))
        self._voice_similarity.setText(str(voice.similarity))
        self._voice_output_format.setText(voice.output_format or "mp3")
        self._sync_voice_provider_fields()

        movie = app.config.movie
        self._movie_ffmpeg.setText(movie.ffmpeg_path)
        profile_index = self._movie_profile.findData(movie.profile)
        if profile_index >= 0:
            self._movie_profile.setCurrentIndex(profile_index)
        transition_index = self._movie_transition.findData(movie.transition)
        if transition_index >= 0:
            self._movie_transition.setCurrentIndex(transition_index)
        motion_index = self._movie_motion.findData(movie.motion)
        if motion_index >= 0:
            self._movie_motion.setCurrentIndex(motion_index)
        self._movie_duration.setText(str(movie.default_duration_sec))
        self._movie_width.setText(str(movie.width))
        self._movie_height.setText(str(movie.height))
        self._movie_fps.setText(str(movie.fps))
        self._movie_codec.setText(movie.codec)
        self._movie_preset.setText(movie.quality_preset)
        self._movie_crf.setText(str(movie.crf))
        keep_index = self._movie_keep_scenes.findData(movie.keep_scene_renders)
        if keep_index >= 0:
            self._movie_keep_scenes.setCurrentIndex(keep_index)

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

    def _selected_voice_provider_id(self) -> str:
        return str(self._voice_provider.currentData() or LOCAL_VOICE_PROVIDER_ID)

    def _is_local_voice_selected(self) -> bool:
        return self._selected_voice_provider_id().casefold() == LOCAL_VOICE_PROVIDER_ID

    def _sync_voice_provider_fields(self, *_args) -> None:
        local = self._is_local_voice_selected()
        # Cloud-only knobs — Local Voice Engine does not need an API key.
        for widget in (
            self._voice_api_key_label,
            self._voice_api_key,
            self._voice_model_label,
            self._voice_model,
            self._voice_stability_label,
            self._voice_stability,
            self._voice_style_label,
            self._voice_style,
            self._voice_similarity_label,
            self._voice_similarity,
        ):
            widget.setVisible(not local)
        if local:
            self._voice_hint.setText(
                "Local Voice Engine is temporarily unavailable on Python 3.13 "
                "until a compatible free backend is selected. "
                "Optional cloud providers can be configured below."
            )
            if not self._voice_output_format.text().strip():
                self._voice_output_format.setText("mp3")
        else:
            self._voice_hint.setText(
                "Cloud voice providers are optional. "
                "A valid API key is required for the selected service."
            )

    def _build_voice_provider(self, settings: VoiceSettings):
        if self._is_local_voice_selected():
            return LocalVoiceProvider(settings)
        return ElevenLabsVoiceProvider(settings)

    def _read_voice_settings(self) -> VoiceSettings:
        voice_id = ""
        voice_name = ""
        data = self._voice_voice.currentData()
        if isinstance(data, str) and data.strip():
            voice_id = data.strip()
            voice_name = self._voice_voice.currentText().strip()
        else:
            text = self._voice_voice.currentText().strip()
            if text.endswith(")") and "(" in text:
                voice_name = text.rsplit("(", 1)[0].strip()
                voice_id = text.rsplit("(", 1)[1].rstrip(")").strip()
            else:
                voice_id = text
                voice_name = text
        return VoiceSettings.from_mapping(
            {
                "api_key": self._voice_api_key.text(),
                "voice_id": voice_id,
                "voice_name": voice_name,
                "language": self._voice_language.text(),
                "model": self._voice_model.currentText(),
                "stability": self._voice_stability.text(),
                "style": self._voice_style.text(),
                "speed": self._voice_speed.text(),
                "similarity": self._voice_similarity.text(),
                "output_format": self._voice_output_format.text(),
            }
        )

    def _test_voice(self) -> None:
        settings = self._read_voice_settings()
        local = self._is_local_voice_selected()
        self._status.setText(
            "Testing Local Voice Engine…" if local else "Testing cloud voice provider…"
        )
        app = self._app()
        if app is not None:
            app.processEvents()
        provider = self._build_voice_provider(settings)
        try:
            message = provider.test_connection()
            voices = provider.list_voices()
            models = provider.list_models()
        except ProviderError as exc:
            self._status.setText(str(exc))
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return

        preferred_id = settings.voice_id
        preferred_name = settings.voice_name
        self._voice_voice.blockSignals(True)
        self._voice_voice.clear()
        for voice in voices:
            label = voice.name
            if voice.language:
                label = f"{voice.name} ({voice.language})"
            self._voice_voice.addItem(label, voice.voice_id)
        if preferred_id:
            index = self._voice_voice.findData(preferred_id)
            if index >= 0:
                self._voice_voice.setCurrentIndex(index)
            else:
                display = preferred_name or preferred_id
                self._voice_voice.addItem(display, preferred_id)
                self._voice_voice.setCurrentIndex(self._voice_voice.count() - 1)
        elif self._voice_voice.count() > 0:
            self._voice_voice.setCurrentIndex(0)
        self._voice_voice.blockSignals(False)

        preferred_model = self._voice_model.currentText().strip()
        self._set_combo_models(self._voice_model, models, preferred=preferred_model)
        self._status.setText(message)
        if app is not None:
            title = "Local Voice Ready" if local else "Voice Provider Connected"
            app.show_notification(title, message)

    def _save_voice(self) -> None:
        app = self._app()
        if app is None:
            return
        settings = self._read_voice_settings()
        provider_id = self._selected_voice_provider_id()
        local = provider_id.casefold() == LOCAL_VOICE_PROVIDER_ID
        if not local and not settings.api_key:
            QMessageBox.warning(
                self,
                "Atlas Studio",
                "Enter an API key for this cloud provider, or switch to Local Voice Engine.",
            )
            return
        if not settings.voice_id:
            QMessageBox.warning(
                self,
                "Atlas Studio",
                "No voice selected. Click Test Connection to load available voices.",
            )
            return
        app.config.voice_provider = provider_id
        app.config.voice = settings
        app.config.save()
        app.rebuild_production_engine()
        label = settings.voice_name or settings.voice_id
        kind = "Local Voice Engine" if local else provider_id
        self._status.setText(f"Voice settings saved ({kind}: {label}).")
        app.show_notification("Voice Settings Saved", f"{kind} · {label}")

    def _read_movie_settings(self) -> MovieSettings:
        return MovieSettings.from_mapping(
            {
                "ffmpeg_path": self._movie_ffmpeg.text(),
                "profile": self._movie_profile.currentData(),
                "transition": self._movie_transition.currentData(),
                "motion": self._movie_motion.currentData(),
                "default_duration_sec": self._movie_duration.text(),
                "width": self._movie_width.text(),
                "height": self._movie_height.text(),
                "fps": self._movie_fps.text(),
                "codec": self._movie_codec.text(),
                "quality_preset": self._movie_preset.text(),
                "crf": self._movie_crf.text(),
                "keep_scene_renders": bool(self._movie_keep_scenes.currentData()),
            }
        )

    def _test_ffmpeg(self) -> None:
        settings = self._read_movie_settings()
        self._status.setText("Testing FFmpeg…")
        app = self._app()
        if app is not None:
            app.processEvents()
        try:
            message = FFmpegProcess(settings.ffmpeg_path).validate()
        except ProviderError as exc:
            self._status.setText(str(exc))
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._status.setText(message)
        if app is not None:
            app.show_notification("FFmpeg Ready", message)

    def _save_movie(self) -> None:
        app = self._app()
        if app is None:
            return
        settings = self._read_movie_settings()
        app.config.movie = settings
        app.config.save()
        app.rebuild_production_engine()
        profile = settings.resolved_profile()
        self._status.setText(
            f"Movie settings saved ({profile.label}, {profile.width}×{profile.height})."
        )
        app.show_notification("Movie Settings Saved", profile.label)

    def _set_voice_combo(self, voice_id: str, voice_name: str) -> None:
        self._voice_voice.blockSignals(True)
        self._voice_voice.clear()
        if voice_id:
            label = voice_name or voice_id
            self._voice_voice.addItem(label, voice_id)
            self._voice_voice.setCurrentIndex(0)
        self._voice_voice.blockSignals(False)

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
