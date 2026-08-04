"""Settings page — Project Root, AI text, Image, Voice providers, About."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
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
from app.providers.errors import ProviderError
from app.providers.forge import ForgeImageProvider
from app.providers.gemini import discover_text_models
from app.providers.kokoro import (
    KOKORO_PROVIDER_ID,
    KOKORO_PROVIDER_LABEL,
)
from app.providers.local_voice import LOCAL_VOICE_PROVIDER_ID
from app.providers.chatterbox import CHATTERBOX_PROVIDER_ID, CHATTERBOX_PROVIDER_LABEL
from app.render.ffmpeg import FFmpegProcess
from app.ui.dialogs.about_dialog import AboutDialog
# TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
# from app.ui.settings.cards.thumbnail_studio_card import ThumbnailStudioCard
from app.ui.voice_health_display import (
    VoiceHealthDisplay,
    display_from_kokoro_health,
    probe_kokoro_quick,
)
from app.ui.widgets.voice_library import VoiceLibraryWidget
from app.providers.voice_base import VoiceInfo


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")
        self._pending_voice_id = ""
        self._pending_voice_name = ""
        self._voice_persist_enabled = True
        self._hf_migration_offered = False
        self._thumbnail_style = None

        title = QLabel("Settings")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Application settings only — Project Root, language of the app, and developer tools.\n"
            "Voice, AI, image style, and movie defaults live on each Channel."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

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

        storage_label = QLabel("AI Storage")
        storage_label.setObjectName("SectionLabel")
        storage_hint = QLabel(
            "Atlas owns all AI model downloads. Hugging Face, Chatterbox, Whisper, "
            "Forge, and Ollama caches live under this folder — never "
            r"C:\Users\<user>\.cache\huggingface."
        )
        storage_hint.setObjectName("PageSubtitle")
        storage_hint.setWordWrap(True)

        models_folder_caption = QLabel("AI Models Folder")
        models_folder_caption.setObjectName("PageSubtitle")
        self._ai_models_input = QLineEdit()
        self._ai_models_input.setPlaceholderText(r"D:\AI\Models")
        browse_models = QPushButton("Browse")
        browse_models.clicked.connect(self._browse_ai_models)
        open_models = QPushButton("Open Folder")
        open_models.clicked.connect(self._open_ai_models_folder)
        models_row = QHBoxLayout()
        models_row.addWidget(self._ai_models_input, stretch=1)
        models_row.addWidget(browse_models)
        models_row.addWidget(open_models)

        save_storage = QPushButton("Save AI Storage")
        save_storage.setObjectName("PrimaryButton")
        save_storage.clicked.connect(self._save_ai_storage)
        migrate_hf = QPushButton("Move Hugging Face Cache…")
        migrate_hf.clicked.connect(self._migrate_hf_cache)
        download_chatterbox = QPushButton("Download Chatterbox Model…")
        download_chatterbox.clicked.connect(self._download_chatterbox_model)
        storage_actions = QHBoxLayout()
        storage_actions.addWidget(save_storage)
        storage_actions.addWidget(migrate_hf)
        storage_actions.addWidget(download_chatterbox)
        storage_actions.addStretch()

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
        self._forge_launch_path = QLineEdit()
        self._forge_launch_path.setPlaceholderText(
            "Path to webui-user.bat / webui.bat (required for auto-start)"
        )
        self._forge_auto_start = QCheckBox("Automatically start Forge when Atlas starts")
        self._forge_auto_start.setChecked(True)
        self._forge_close_on_exit = QCheckBox("Close Forge when Atlas exits")
        self._forge_close_on_exit.setToolTip(
            "Only applies when Atlas started Forge. Prefills the exit confirmation."
        )

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
        launch_row = QHBoxLayout()
        launch_row.addWidget(self._forge_launch_path, stretch=1)
        browse_launch = QPushButton("Browse…")
        browse_launch.clicked.connect(self._browse_forge_launch)
        launch_row.addWidget(browse_launch)
        forge_form.addRow("Launch Path", launch_row)
        forge_form.addRow("", self._forge_auto_start)
        forge_form.addRow("", self._forge_close_on_exit)

        self._forge_section_anchor = image_label

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
        self._voice_provider.addItem(KOKORO_PROVIDER_LABEL, KOKORO_PROVIDER_ID)
        self._voice_provider.addItem(CHATTERBOX_PROVIDER_LABEL, CHATTERBOX_PROVIDER_ID)
        self._voice_provider.addItem("ElevenLabs (Optional)", "elevenlabs")
        # Future optional cloud plugins: OpenAI, Azure, Google, …
        self._voice_provider.currentIndexChanged.connect(self._sync_voice_provider_fields)

        # Inline provider health — never uses popup dialogs.
        health_panel = QWidget()
        health_panel.setObjectName("VoiceHealthPanel")
        health_layout = QVBoxLayout(health_panel)
        health_layout.setContentsMargins(0, 6, 0, 4)
        health_layout.setSpacing(4)
        self._voice_health_status = QLabel("⚪ Checking…")
        self._voice_health_status.setObjectName("VoiceHealthStatus")
        self._voice_health_detail = QLabel("")
        self._voice_health_detail.setObjectName("VoiceHealthDetail")
        self._voice_health_detail.setWordWrap(True)
        health_layout.addWidget(self._voice_health_status)
        health_layout.addWidget(self._voice_health_detail)

        # Reserved for future Repair / Download Models / Test Provider actions.
        self._voice_health_actions = QHBoxLayout()
        self._voice_health_actions.setContentsMargins(0, 2, 0, 2)
        self._voice_health_actions.setSpacing(8)
        self._voice_health_actions.addStretch()

        self._voice_api_key = QLineEdit()
        self._voice_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._voice_api_key.setPlaceholderText("Required for cloud providers only")

        library_label = QLabel("Voice Library")
        library_label.setObjectName("SectionLabel")
        self._voice_library = VoiceLibraryWidget()
        self._voice_library.voice_selected.connect(self._on_voice_library_selected)

        self._voice_language = QLineEdit()
        self._voice_language.setPlaceholderText("e.g. en-US")
        self._voice_model = QComboBox()
        self._voice_model.setEditable(True)
        self._voice_stability = QLineEdit()
        self._voice_style = QLineEdit()
        self._voice_speed = QLineEdit()
        self._voice_similarity = QLineEdit()
        self._voice_output_format = QLineEdit()
        self._voice_output_format.setPlaceholderText("wav (Kokoro) or mp3 (cloud)")

        self._voice_hint = QLabel(
            "Kokoro works offline and requires no subscription. "
            "Install local deps with requirements-voice-local.txt. "
            "Cloud providers are optional."
        )
        self._voice_hint.setObjectName("PageSubtitle")
        self._voice_hint.setWordWrap(True)

        # Chatterbox reference-clip library — absolute path scanned for wav/mp3.
        self._chatterbox_folder_host = QWidget()
        chatterbox_folder_layout = QVBoxLayout(self._chatterbox_folder_host)
        chatterbox_folder_layout.setContentsMargins(0, 4, 0, 4)
        chatterbox_folder_layout.setSpacing(6)
        self._chatterbox_folder_label = QLabel("Chatterbox Voices Folder:")
        self._chatterbox_folder_label.setObjectName("SectionLabel")
        self._chatterbox_folder_path = QLabel("")
        self._chatterbox_folder_path.setObjectName("PageSubtitle")
        self._chatterbox_folder_path.setWordWrap(True)
        self._chatterbox_folder_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._chatterbox_open_folder = QPushButton("Open Folder")
        self._chatterbox_open_folder.setObjectName("SecondaryButton")
        self._chatterbox_open_folder.clicked.connect(self._open_chatterbox_voices_folder)
        chatterbox_folder_row = QHBoxLayout()
        chatterbox_folder_row.setContentsMargins(0, 0, 0, 0)
        chatterbox_folder_row.addWidget(self._chatterbox_open_folder)
        chatterbox_folder_row.addStretch()
        chatterbox_folder_layout.addWidget(self._chatterbox_folder_label)
        chatterbox_folder_layout.addWidget(self._chatterbox_folder_path)
        chatterbox_folder_layout.addLayout(chatterbox_folder_row)
        self._chatterbox_folder_host.hide()

        voice_form = QFormLayout()
        self._voice_api_key_label = QLabel("API Key")
        voice_form.addRow(self._voice_api_key_label, self._voice_api_key)
        self._voice_model_label = QLabel("Model")
        voice_form.addRow(self._voice_model_label, self._voice_model)
        self._voice_stability_label = QLabel("Stability")
        voice_form.addRow(self._voice_stability_label, self._voice_stability)
        self._voice_style_label = QLabel("Style")
        voice_form.addRow(self._voice_style_label, self._voice_style)
        voice_form.addRow("Language", self._voice_language)
        voice_form.addRow("Speed", self._voice_speed)
        self._voice_similarity_label = QLabel("Similarity")
        voice_form.addRow(self._voice_similarity_label, self._voice_similarity)
        voice_form.addRow("Output Format", self._voice_output_format)

        test_voice = QPushButton("Test Provider")
        test_voice.clicked.connect(self._test_voice)
        refresh_voices = QPushButton("Refresh Voices")
        refresh_voices.clicked.connect(self._refresh_voice_library)
        save_voice = QPushButton("Save Voice Settings")
        save_voice.setObjectName("PrimaryButton")
        save_voice.clicked.connect(self._save_voice)
        voice_actions = QHBoxLayout()
        voice_actions.addWidget(test_voice)
        voice_actions.addWidget(refresh_voices)
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

        # Advanced movie encoding — hidden by default toggle.
        self._movie_advanced_host = QWidget()
        movie_advanced = QFormLayout(self._movie_advanced_host)
        movie_advanced.setContentsMargins(0, 0, 0, 0)
        movie_advanced.addRow("Custom Width", self._movie_width)
        movie_advanced.addRow("Custom Height", self._movie_height)
        movie_advanced.addRow("FPS", self._movie_fps)
        movie_advanced.addRow("Codec", self._movie_codec)
        movie_advanced.addRow("Quality Preset", self._movie_preset)
        movie_advanced.addRow("CRF", self._movie_crf)
        movie_advanced.addRow("Keep Scene Renders", self._movie_keep_scenes)
        self._movie_advanced_host.hide()

        self._movie_advanced_toggle = QCheckBox("Show advanced movie options")
        self._movie_advanced_toggle.toggled.connect(self._movie_advanced_host.setVisible)

        test_movie = QPushButton("Test FFmpeg")
        test_movie.clicked.connect(self._test_ffmpeg)
        save_movie = QPushButton("Save Movie Settings")
        save_movie.setObjectName("PrimaryButton")
        save_movie.clicked.connect(self._save_movie)
        movie_actions = QHBoxLayout()
        movie_actions.addWidget(test_movie)
        movie_actions.addWidget(save_movie)
        movie_actions.addStretch()

        self._thumbnail_style = None
        # TODO V3.1
        # Restore Thumbnail Generator after new AI workflow.
        # from app.ui.settings.cards.thumbnail_studio_card import ThumbnailStudioCard
        # self._thumbnail_style = ThumbnailStudioCard()

        developer_label = QLabel("Advanced")
        developer_label.setObjectName("SectionLabel")
        advanced_hint = QLabel(
            "Occasional options — leave defaults unless you need them."
        )
        advanced_hint.setObjectName("PageSubtitle")
        advanced_hint.setWordWrap(True)
        self._developer_mode = QCheckBox("Developer Mode")
        self._developer_mode.setToolTip(
            "When enabled, Atlas shows the startup timeline after launch "
            "and writes detailed profiles to logs/."
        )
        self._developer_mode.toggled.connect(self._on_developer_mode_toggled)
        view_timeline = QPushButton("View Startup Timeline")
        view_timeline.clicked.connect(self._view_startup_timeline)
        developer_actions = QHBoxLayout()
        developer_actions.addWidget(view_timeline)
        developer_actions.addStretch()

        about_button = QPushButton("About Atlas Studio")
        about_button.clicked.connect(self.open_about)

        self._status = QLabel("")
        self._status.setObjectName("PageSubtitle")
        self._status.setWordWrap(True)
        self._voice_library.status_message.connect(self._status.setText)

        # AI Providers live in Settings only (disconnected from sidebar).
        from app.ui.pages.ai_providers_page import AIProvidersPage

        ai_roles_label = QLabel("AI Providers & Roles")
        ai_roles_label.setObjectName("SectionLabel")
        ai_roles_hint = QLabel(
            "Configure providers once. The production workflow uses them automatically — "
            "no model choices during Generate."
        )
        ai_roles_hint.setObjectName("PageSubtitle")
        ai_roles_hint.setWordWrap(True)
        self._ai_providers = AIProvidersPage()

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
        layout.addWidget(storage_label)
        layout.addWidget(storage_hint)
        layout.addWidget(models_folder_caption)
        layout.addLayout(models_row)
        layout.addLayout(storage_actions)
        layout.addSpacing(20)

        # Channel-owned production config moved to Channel Settings.
        # Keep machine connections / API keys as application fallbacks.
        fallbacks_toggle = QCheckBox(
            "Show application connections (API keys, Forge, Voice library)"
        )
        fallbacks_hint = QLabel(
            "Per-channel voice, AI model, and image style are edited under "
            "Channels → Channel Settings. These fields are machine-level fallbacks."
        )
        fallbacks_hint.setObjectName("PageSubtitle")
        fallbacks_hint.setWordWrap(True)

        self._fallbacks_host = QWidget()
        fallbacks = QVBoxLayout(self._fallbacks_host)
        fallbacks.setContentsMargins(0, 0, 0, 0)
        fallbacks.setSpacing(12)
        fallbacks.addWidget(ai_label)
        fallbacks.addWidget(self._provider)
        fallbacks.addWidget(key_label)
        fallbacks.addWidget(self._api_key)
        fallbacks.addWidget(model_label)
        fallbacks.addWidget(self._model)
        fallbacks.addLayout(ai_actions)
        fallbacks.addSpacing(12)
        fallbacks.addWidget(ai_roles_label)
        fallbacks.addWidget(ai_roles_hint)
        fallbacks.addWidget(self._ai_providers)
        fallbacks.addSpacing(12)
        fallbacks.addWidget(image_label)
        fallbacks.addWidget(self._image_provider)
        fallbacks.addLayout(forge_form)
        fallbacks.addLayout(forge_actions)
        fallbacks.addSpacing(12)
        fallbacks.addWidget(voice_label)
        fallbacks.addWidget(self._voice_provider)
        fallbacks.addWidget(health_panel)
        fallbacks.addLayout(self._voice_health_actions)
        fallbacks.addWidget(self._voice_hint)
        fallbacks.addWidget(self._chatterbox_folder_host)
        fallbacks.addWidget(library_label)
        fallbacks.addWidget(self._voice_library)
        fallbacks.addLayout(voice_form)
        fallbacks.addLayout(voice_actions)
        fallbacks.addSpacing(12)
        fallbacks.addWidget(movie_label)
        fallbacks.addLayout(movie_form)
        fallbacks.addWidget(self._movie_advanced_toggle)
        fallbacks.addWidget(self._movie_advanced_host)
        fallbacks.addLayout(movie_actions)
        self._fallbacks_host.hide()
        fallbacks_toggle.toggled.connect(self._fallbacks_host.setVisible)

        layout.addWidget(fallbacks_toggle)
        layout.addWidget(fallbacks_hint)
        layout.addWidget(self._fallbacks_host)
        layout.addSpacing(20)
        # TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
        # layout.addWidget(self._thumbnail_style)
        # layout.addSpacing(20)
        layout.addWidget(developer_label)
        layout.addWidget(advanced_hint)
        layout.addWidget(self._developer_mode)
        layout.addLayout(developer_actions)
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
        # TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
        if self._thumbnail_style is not None:
            self._thumbnail_style.refresh()
        self._maybe_offer_hf_migration()

    def open_about(self) -> None:
        AboutDialog(self).exec()

    def _on_developer_mode_toggled(self, checked: bool) -> None:
        app = self._app()
        if app is None:
            return
        app.config.developer_mode = bool(checked)
        try:
            app.config.save()
            self._status.setText(
                "Developer Mode on — startup timeline will open after next launch."
                if checked
                else "Developer Mode off."
            )
        except OSError as exc:
            self._status.setText(f"Could not save Developer Mode: {exc}")

    def _view_startup_timeline(self) -> None:
        from app.ui.dialogs.startup_timeline_dialog import StartupTimelineDialog

        app = self._app()
        profile = app.startup_profile if app is not None else None
        StartupTimelineDialog(profile, parent=self).exec()

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _load_current(self) -> None:
        app = self._app()
        if app is None:
            return
        current = app.config.project_root
        self._root_input.setText(str(current) if current else "")
        models_root = getattr(app.config, "ai_models_root", None)
        if models_root is not None:
            self._ai_models_input.setText(str(models_root))
        else:
            from app.core.ai_storage import default_ai_models_root

            self._ai_models_input.setText(str(default_ai_models_root()))
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
        self._forge_launch_path.setText(forge.launch_path)
        self._forge_auto_start.setChecked(bool(forge.auto_start_forge))
        self._forge_close_on_exit.setChecked(bool(forge.close_forge_on_exit))

        self._developer_mode.blockSignals(True)
        self._developer_mode.setChecked(bool(app.config.developer_mode))
        self._developer_mode.blockSignals(False)

        voice_provider = app.config.voice_provider or KOKORO_PROVIDER_ID
        if voice_provider.casefold() in {LOCAL_VOICE_PROVIDER_ID, "kokoro"}:
            voice_provider = KOKORO_PROVIDER_ID
        voice_index = self._voice_provider.findData(voice_provider)
        if voice_index >= 0:
            self._voice_provider.setCurrentIndex(voice_index)

        voice = app.config.voice
        self._voice_api_key.setText(voice.api_key)
        self._pending_voice_id = voice.voice_id
        self._pending_voice_name = voice.voice_name
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
        self._refresh_voice_library()

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

    def _browse_ai_models(self) -> None:
        start = self._ai_models_input.text().strip() or r"D:\AI\Models"
        chosen = QFileDialog.getExistingDirectory(self, "Select AI Models Folder", start)
        if chosen:
            self._ai_models_input.setText(chosen)

    def _open_ai_models_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from app.core.ai_storage import ensure_ai_models_layout

        text = self._ai_models_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Atlas Studio", "Choose an AI Models folder first.")
            return
        try:
            folder = ensure_ai_models_layout(Path(text))
        except OSError as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        if not opened:
            QMessageBox.warning(self, "Atlas Studio", f"Could not open folder:\n{folder}")

    def _save_ai_storage(self) -> None:
        app = self._app()
        if app is None:
            return
        text = self._ai_models_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Atlas Studio", "Choose an AI Models folder.")
            return
        from app.core.ai_storage import apply_ai_storage_environment, ensure_ai_models_layout

        try:
            resolved = ensure_ai_models_layout(Path(text))
        except OSError as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        app.config.ai_models_root = resolved
        app.config.save()
        apply_ai_storage_environment(resolved)
        self._ai_models_input.setText(str(resolved))
        self._status.setText(f"AI Models Folder: {resolved}")
        app.show_notification("AI Storage Saved", str(resolved))

    def _migrate_hf_cache(self) -> None:
        from app.core import ai_storage
        from app.ui.dialogs.hf_migration_dialog import (
            HuggingFaceMigrationDialog,
            offer_legacy_hf_migration,
        )

        if not ai_storage.legacy_hf_cache_has_content():
            QMessageBox.information(
                self,
                "Atlas Studio",
                "No models were found in the Windows default Hugging Face cache:\n\n"
                f"{ai_storage.legacy_huggingface_cache()}",
            )
            return
        # Prefer the current input path for destination root.
        text = self._ai_models_input.text().strip()
        if text:
            ai_storage.ensure_ai_models_layout(Path(text))
            dest = ai_storage.huggingface_dir(Path(text))
            dialog = HuggingFaceMigrationDialog(self, destination=dest)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result is not None:
                result = dialog.result
                self._status.setText(
                    f"Moved {result.moved} item(s) to {result.destination}"
                )
            return
        offer_legacy_hf_migration(self)

    def _download_chatterbox_model(self) -> None:
        from app.ui.dialogs.chatterbox_model_dialog import ensure_chatterbox_model

        text = self._ai_models_input.text().strip()
        root = Path(text) if text else None
        if root is not None:
            from app.core.ai_storage import apply_ai_storage_environment

            try:
                apply_ai_storage_environment(root)
            except OSError as exc:
                QMessageBox.warning(self, "Atlas Studio", str(exc))
                return
        if ensure_chatterbox_model(self):
            self._status.setText("Chatterbox model is ready.")
        else:
            self._status.setText("Chatterbox model is not installed yet.")

    def _maybe_offer_hf_migration(self) -> None:
        if getattr(self, "_hf_migration_offered", False):
            return
        self._hf_migration_offered = True
        from app.core import ai_storage
        from app.ui.dialogs.hf_migration_dialog import offer_legacy_hf_migration

        if not ai_storage.legacy_hf_cache_has_content():
            return
        # Only prompt when Atlas HuggingFace folder looks empty.
        dest = ai_storage.huggingface_dir()
        try:
            has_atlas = dest.is_dir() and any(dest.iterdir())
        except OSError:
            has_atlas = False
        if has_atlas:
            return
        result = offer_legacy_hf_migration(self)
        if result is not None:
            self._status.setText(
                f"Moved {result.moved} item(s) to {result.destination}"
            )

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
                "launch_path": self._forge_launch_path.text(),
                "auto_start_forge": self._forge_auto_start.isChecked(),
                "close_forge_on_exit": self._forge_close_on_exit.isChecked(),
            }
        )

    def _browse_forge_launch(self) -> None:
        start = self._forge_launch_path.text().strip() or str(Path.home())
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Select Forge Launch Script",
            start,
            "Launch scripts (*.bat *.cmd *.ps1 *.sh *);;All files (*.*)",
        )
        if chosen:
            self._forge_launch_path.setText(chosen)

    def focus_forge_section(self) -> None:
        """Bring the Image Provider / Forge section into view."""
        host = getattr(self, "_fallbacks_host", None)
        if host is not None:
            host.show()
        anchor = getattr(self, "_forge_section_anchor", None)
        if anchor is not None:
            anchor.setFocus(Qt.FocusReason.OtherFocusReason)
            parent = anchor.parentWidget()
            while parent is not None:
                if isinstance(parent, QScrollArea):
                    parent.ensureWidgetVisible(anchor)
                    break
                parent = parent.parentWidget()
        self._forge_host.setFocus(Qt.FocusReason.OtherFocusReason)

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
        app.forge_status.update_settings(settings)
        if settings.auto_start_forge and not app.forge_status.probe_online():
            app.forge_status.ensure_running_if_configured()
        self._status.setText(
            f"Image settings saved ({settings.host}:{settings.port}, {settings.width}×{settings.height})."
        )
        app.show_notification("Image Settings Saved", settings.model or "Forge")

    def _selected_voice_provider_id(self) -> str:
        return str(self._voice_provider.currentData() or KOKORO_PROVIDER_ID)

    def _is_kokoro_selected(self) -> bool:
        selected = self._selected_voice_provider_id().casefold()
        return selected in {KOKORO_PROVIDER_ID, LOCAL_VOICE_PROVIDER_ID}

    def _is_local_voice_selected(self) -> bool:
        selected = self._selected_voice_provider_id().casefold()
        return selected in {
            KOKORO_PROVIDER_ID,
            LOCAL_VOICE_PROVIDER_ID,
            CHATTERBOX_PROVIDER_ID,
        }

    def _sync_voice_provider_fields(self, *_args) -> None:
        local = self._is_local_voice_selected()
        kokoro = self._is_kokoro_selected()
        chatterbox = self._selected_voice_provider_id().casefold() == CHATTERBOX_PROVIDER_ID
        # Cloud-only knobs — local providers do not need an API key.
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
        if kokoro:
            self._chatterbox_folder_host.hide()
            self._voice_hint.setText(
                "Kokoro (ONNX) is the default local voice provider (offline, free). "
                "Install with: pip install -r requirements-voice-local.txt "
                "(Python 3.10–3.13). Model files download into Cache/kokoro on first use. "
                "Optional Chatterbox or cloud providers can be selected above."
            )
            if not self._voice_output_format.text().strip():
                self._voice_output_format.setText("wav")
        elif chatterbox:
            self._update_chatterbox_folder_ui()
            self._chatterbox_folder_host.show()
            models = self._chatterbox_folder_path.text().strip() or "voices/chatterbox"
            self._voice_hint.setText(
                "Chatterbox is the second local voice provider (Resemble AI). "
                "Install with: pip install chatterbox-tts "
                f"(or requirements-voice-local.txt). Optional reference clips in:\n{models}\n"
                "Model weights download into Settings → AI Storage (never the Windows HF cache). "
                "Voices are discovered from the installed package — nothing is hardcoded."
            )
            if not self._voice_output_format.text().strip():
                self._voice_output_format.setText("wav")
        else:
            self._chatterbox_folder_host.hide()
            self._voice_hint.setText(
                "Cloud voice providers are optional. "
                "A valid API key is required for the selected service."
            )
        self._refresh_voice_health(full=False)
        self._refresh_voice_library()

    def _chatterbox_voices_folder(self) -> Path | None:
        """Absolute folder for optional Chatterbox reference clips."""
        discovery = self._voice_discovery()
        if discovery is None:
            return None
        return discovery.chatterbox_voices_dir()

    def _update_chatterbox_folder_ui(self) -> None:
        folder = self._chatterbox_voices_folder()
        if folder is None:
            self._chatterbox_folder_path.setText("(Application is not ready)")
            self._chatterbox_open_folder.setEnabled(False)
            return
        folder.mkdir(parents=True, exist_ok=True)
        self._chatterbox_folder_path.setText(str(folder.resolve()))
        self._chatterbox_open_folder.setEnabled(True)

    def _open_chatterbox_voices_folder(self) -> None:
        folder = self._chatterbox_voices_folder()
        if folder is None:
            self._status.setText("Application is not ready.")
            return
        folder.mkdir(parents=True, exist_ok=True)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))
        if opened:
            self._status.setText(f"Opened Chatterbox voices folder: {folder.resolve()}")
        else:
            self._status.setText(f"Could not open folder: {folder.resolve()}")

    def _kokoro_model_dir(self):
        app = self._app()
        if app is None:
            return None
        from app.providers.voice_discovery import VoiceDiscoveryService

        return VoiceDiscoveryService(app.config).kokoro_model_dir()

    def _voice_discovery(self):
        app = self._app()
        if app is None:
            return None
        from app.providers.voice_discovery import VoiceDiscoveryService

        return VoiceDiscoveryService(app.config)

    def _apply_voice_health(self, display: VoiceHealthDisplay) -> None:
        self._voice_health_status.setText(display.headline)
        self._voice_health_detail.setText(display.detail)
        self._voice_health_detail.setVisible(bool(display.detail.strip()))

    def _refresh_voice_health(self, *, full: bool) -> None:
        if self._is_kokoro_selected():
            model_dir = self._kokoro_model_dir()
            if model_dir is None:
                self._apply_voice_health(
                    VoiceHealthDisplay(
                        "idle",
                        "Unavailable",
                        "Open Settings after the app finishes starting.",
                    )
                )
                return
            if full:
                self._apply_voice_health(
                    VoiceHealthDisplay(
                        "busy",
                        "Checking Kokoro…",
                        "Verifying package, runtime, models, and synthesis.",
                    )
                )
                app = self._app()
                if app is not None:
                    app.processEvents()
                # Show download state if models are missing before health_check runs.
                model_ok = (model_dir / "kokoro-v1.0.onnx").is_file()
                voices_ok = (model_dir / "voices-v1.0.bin").is_file()
                if not model_ok or not voices_ok:
                    self._apply_voice_health(
                        VoiceHealthDisplay(
                            "busy",
                            "Downloading models…",
                            "Fetching Kokoro ONNX model files into Cache/kokoro.",
                        )
                    )
                    if app is not None:
                        app.processEvents()
                provider = self._build_voice_provider(self._read_voice_settings())
                health = provider.health_check()
                self._apply_voice_health(display_from_kokoro_health(health))
                return
            self._apply_voice_health(probe_kokoro_quick(model_dir=model_dir))
            return

        if self._selected_voice_provider_id().casefold() == CHATTERBOX_PROVIDER_ID:
            discovery = self._voice_discovery()
            if discovery is None:
                self._apply_voice_health(
                    VoiceHealthDisplay(
                        "idle",
                        "Unavailable",
                        "Open Settings after the app finishes starting.",
                    )
                )
                return
            try:
                result = discovery.discover(provider_id=CHATTERBOX_PROVIDER_ID)
            except Exception as exc:  # noqa: BLE001
                self._apply_voice_health(
                    VoiceHealthDisplay("error", "Chatterbox error", str(exc))
                )
                return
            if not result.ok:
                self._apply_voice_health(
                    VoiceHealthDisplay(
                        "warn",
                        "Chatterbox not ready",
                        result.empty_message,
                    )
                )
            else:
                voices_dir = result.model_dir or str(discovery.chatterbox_voices_dir())
                self._apply_voice_health(
                    VoiceHealthDisplay(
                        "ok",
                        "Chatterbox ready",
                        f"{len(result.voices)} voice(s) discovered. "
                        f"Reference clips folder: {voices_dir}.",
                    )
                )
            return

        # Cloud provider — lightweight readiness without dialogs.
        settings = self._read_voice_settings()
        if not settings.api_key.strip():
            self._apply_voice_health(
                VoiceHealthDisplay(
                    "warn",
                    "API key required",
                    "Enter an API key for this cloud provider, or switch to Kokoro / Chatterbox.",
                )
            )
            return
        self._apply_voice_health(
            VoiceHealthDisplay(
                "idle",
                "Cloud provider selected",
                "Click Test Provider to verify the connection and load voices.",
            )
        )

    def _build_voice_provider(self, settings: VoiceSettings):
        discovery = self._voice_discovery()
        if discovery is None:
            from app.providers.errors import ProviderConfigurationError

            raise ProviderConfigurationError(
                "Application is not ready — cannot resolve the voice provider."
            )
        return discovery.resolve_provider(
            provider_id=self._selected_voice_provider_id(),
            settings=settings,
        )

    def _on_voice_library_selected(self, voice: object) -> None:
        if not isinstance(voice, VoiceInfo):
            return
        self._pending_voice_id = voice.voice_id
        self._pending_voice_name = voice.name
        if voice.language:
            self._voice_language.setText(voice.language)
        self._persist_last_selected_voice(voice)

    def _persist_last_selected_voice(self, voice: VoiceInfo) -> None:
        """Remember the last selected narrator across app restarts."""
        if not self._voice_persist_enabled:
            return
        app = self._app()
        if app is None:
            return
        current = app.config.voice
        provider_id = self._selected_voice_provider_id()
        if (
            current.voice_id == voice.voice_id
            and current.voice_name == voice.name
            and (app.config.voice_provider or "") == provider_id
        ):
            return
        settings = self._read_voice_settings()
        app.config.voice_provider = provider_id
        app.config.voice = settings
        app.config.save()
        app.rebuild_production_engine()

    def _refresh_voice_library(self) -> None:
        settings = self._read_voice_settings()
        discovery = self._voice_discovery()
        if discovery is None:
            self._voice_library.clear()
            self._voice_library.set_voices(
                [],
                empty_message="Application is not ready — open Settings after startup.",
            )
            self._status.setText("Application is not ready.")
            return

        result = discovery.discover(
            provider_id=self._selected_voice_provider_id(),
            settings=settings,
        )
        try:
            provider = discovery.resolve_provider(
                provider_id=result.provider_id or self._selected_voice_provider_id(),
                settings=settings,
            )
            self._voice_library.set_provider(provider)
        except Exception:  # noqa: BLE001
            self._voice_library.set_provider(None)

        preferred = getattr(self, "_pending_voice_id", "") or settings.voice_id
        self._voice_persist_enabled = False
        try:
            self._voice_library.set_voices(
                result.voices,
                selected_voice_id=preferred,
                language=settings.language,
                empty_message=result.empty_message if not result.ok else result.warning,
            )
        finally:
            self._voice_persist_enabled = True
        selected = self._voice_library.selected_voice()
        if selected is not None:
            self._pending_voice_id = selected.voice_id
            self._pending_voice_name = selected.name
            self._persist_last_selected_voice(selected)
        if not result.ok:
            self._status.setText(result.empty_message)
        elif result.warning:
            self._status.setText(result.warning)
        elif self._voice_library.last_warning:
            pass
        else:
            self._status.setText(f"Loaded {len(result.voices)} voice(s).")

    def _read_voice_settings(self) -> VoiceSettings:
        selected = self._voice_library.selected_voice()
        if selected is not None:
            voice_id = selected.voice_id
            voice_name = selected.name
        else:
            voice_id = getattr(self, "_pending_voice_id", "") or ""
            voice_name = getattr(self, "_pending_voice_name", "") or voice_id
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
        label = self._voice_provider.currentText() or "voice provider"
        self._status.setText(f"Testing {label}…")
        app = self._app()
        if app is not None:
            app.processEvents()
        provider = self._build_voice_provider(settings)
        try:
            if self._is_kokoro_selected() and hasattr(provider, "health_check"):
                health = provider.health_check()
                display = display_from_kokoro_health(health)
                self._apply_voice_health(display)
                if not health.ok:
                    self._status.setText(display.detail or display.title)
                    return
                message = health.message
            else:
                if self._selected_voice_provider_id().casefold() == CHATTERBOX_PROVIDER_ID:
                    from app.providers.chatterbox_install import is_chatterbox_english_installed
                    from app.ui.dialogs.chatterbox_model_dialog import ensure_chatterbox_model

                    if not is_chatterbox_english_installed():
                        if not ensure_chatterbox_model(self):
                            self._apply_voice_health(
                                VoiceHealthDisplay(
                                    "error",
                                    "Chatterbox model missing",
                                    "Download the Chatterbox model to continue.",
                                )
                            )
                            self._status.setText("Chatterbox model not installed.")
                            return
                message = provider.test_connection()
                self._apply_voice_health(
                    VoiceHealthDisplay("ok", "Provider Ready", message)
                )
            voices = provider.list_voices()
            models = provider.list_models()
        except ProviderError as exc:
            from app.ui.dialogs.chatterbox_model_dialog import (
                offer_chatterbox_download_for_error,
            )

            if offer_chatterbox_download_for_error(self, exc):
                return self._test_voice()
            detail = str(exc)
            self._apply_voice_health(
                VoiceHealthDisplay("error", "Provider error", detail)
            )
            self._status.setText(detail)
            return

        self._voice_library.set_provider(provider)
        discovery = self._voice_discovery()
        empty_message = ""
        if not voices and discovery is not None:
            empty_message = discovery.discover(
                provider_id=self._selected_voice_provider_id(),
                settings=settings,
            ).empty_message
        self._voice_library.set_voices(
            voices,
            selected_voice_id=settings.voice_id,
            language=settings.language,
            empty_message=empty_message or "No voices available.",
        )
        if not voices:
            self._status.setText(empty_message or "No voices available.")
        else:
            preferred_model = self._voice_model.currentText().strip()
            self._set_combo_models(self._voice_model, models, preferred=preferred_model)
            self._status.setText(message)

    def _save_voice(self) -> None:
        app = self._app()
        if app is None:
            return
        settings = self._read_voice_settings()
        provider_id = self._selected_voice_provider_id()
        local = self._is_local_voice_selected()
        if provider_id.casefold() in {LOCAL_VOICE_PROVIDER_ID, "kokoro"}:
            provider_id = KOKORO_PROVIDER_ID
        if provider_id.casefold() == CHATTERBOX_PROVIDER_ID:
            provider_id = CHATTERBOX_PROVIDER_ID
        if not local and not settings.api_key:
            message = (
                "Enter an API key for this cloud provider, "
                "or switch to Kokoro / Chatterbox."
            )
            self._apply_voice_health(
                VoiceHealthDisplay("warn", "API key required", message)
            )
            self._status.setText(message)
            return
        if not settings.voice_id:
            message = "No voice selected. Refresh the Voice Library, then choose a narrator."
            self._apply_voice_health(
                VoiceHealthDisplay("warn", "No voice selected", message)
            )
            self._status.setText(message)
            return
        app.config.voice_provider = provider_id
        app.config.voice = settings
        app.config.save()
        app.rebuild_production_engine()
        label = settings.voice_name or settings.voice_id
        kind = self._voice_provider.currentText() or provider_id
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
