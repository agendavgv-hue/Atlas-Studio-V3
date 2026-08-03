"""Channel Settings — per-channel production configuration (master)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.channels.production_profile import ChannelProductionProfile
from app.core.project_root import ProjectRootError


class ChannelSettingsPage(QWidget):
    """Edit one channel’s production profile. Projects inherit a snapshot at create."""

    back_requested = Signal()
    channel_studio_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")
        self._folder: str | None = None

        back = QPushButton("← Channel Dashboard")
        back.setObjectName("SecondaryButton")
        back.clicked.connect(self.back_requested.emit)

        self._title = QLabel("Channel Settings")
        self._title.setObjectName("PageTitle")
        self._hint = QLabel(
            "This channel is the master configuration. New projects copy these "
            "defaults. Existing projects keep their original snapshot."
        )
        self._hint.setObjectName("PageSubtitle")
        self._hint.setWordWrap(True)

        self._tabs = QTabWidget()

        # --- General ---
        general = QWidget()
        gform = QFormLayout(general)
        self._name = QLineEdit()
        self._name.setReadOnly(True)
        self._description = QTextEdit()
        self._description.setFixedHeight(80)
        self._outro = QLineEdit()
        self._intro = QLineEdit()
        self._resolution = QComboBox()
        for label, value in (
            ("1920 × 1080", "1920x1080"),
            ("1280 × 720", "1280x720"),
            ("3840 × 2160", "3840x2160"),
        ):
            self._resolution.addItem(label, value)
        self._output = QLineEdit()
        gform.addRow("Channel", self._name)
        gform.addRow("Description", self._description)
        gform.addRow("Intro line", self._intro)
        gform.addRow("Outro line", self._outro)
        gform.addRow("Default resolution", self._resolution)
        gform.addRow("Output folder", self._output)
        self._tabs.addTab(general, "General")

        # --- Branding ---
        brand = QWidget()
        bform = QFormLayout(brand)
        self._logo = QLineEdit()
        self._banner = QLineEdit()
        self._primary = QLineEdit()
        self._secondary = QLineEdit()
        self._accent = QLineEdit()
        bform.addRow("Logo path", self._logo)
        bform.addRow("Banner path", self._banner)
        bform.addRow("Primary color", self._primary)
        bform.addRow("Secondary color", self._secondary)
        bform.addRow("Accent color", self._accent)
        self._tabs.addTab(brand, "Branding")

        # --- Voice ---
        voice = QWidget()
        vform = QFormLayout(voice)
        self._voice_provider = QComboBox()
        self._voice_provider.addItem("Kokoro", "kokoro")
        self._voice_provider.addItem("ElevenLabs", "elevenlabs")
        self._voice_id = QLineEdit()
        self._voice_name = QLineEdit()
        self._voice_styles = QLineEdit()
        self._voice_speed = QLineEdit()
        vform.addRow("Voice provider", self._voice_provider)
        vform.addRow("Voice id", self._voice_id)
        vform.addRow("Voice name", self._voice_name)
        vform.addRow("Style tags", self._voice_styles)
        vform.addRow("Speed", self._voice_speed)
        self._tabs.addTab(voice, "Voice")

        # --- AI ---
        ai = QWidget()
        aiform = QFormLayout(ai)
        self._ai_provider = QComboBox()
        for label, value in (
            ("Ollama", "ollama"),
            ("Gemini", "gemini"),
            ("OpenAI", "openai"),
            ("Claude", "anthropic"),
        ):
            self._ai_provider.addItem(label, value)
        self._ai_model = QLineEdit()
        aiform.addRow("AI provider", self._ai_provider)
        aiform.addRow("Preferred model", self._ai_model)
        note = QLabel(
            "API keys and machine connections stay in Application Settings. "
            "This channel chooses which provider/model new projects use."
        )
        note.setWordWrap(True)
        note.setObjectName("PageSubtitle")
        aiform.addRow(note)
        self._tabs.addTab(ai, "AI")

        # --- Images / Prompts ---
        images = QWidget()
        iform = QFormLayout(images)
        self._image_style = QLineEdit()
        self._prompt_template = QLineEdit()
        self._image_prompt = QTextEdit()
        self._image_prompt.setFixedHeight(90)
        self._negative = QTextEdit()
        self._negative.setFixedHeight(70)
        iform.addRow("Image style", self._image_style)
        iform.addRow("Prompt template", self._prompt_template)
        iform.addRow("Image prompt", self._image_prompt)
        iform.addRow("Negative prompt", self._negative)
        self._tabs.addTab(images, "Images")

        # --- Movie / Export ---
        movie = QWidget()
        mform = QFormLayout(movie)
        self._movie_notes = QLineEdit()
        self._export_notes = QLineEdit()
        mform.addRow("Movie notes", self._movie_notes)
        mform.addRow("Export notes", self._export_notes)
        self._tabs.addTab(movie, "Movie / Export")

        save = QPushButton("Save Channel Settings")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._save)

        advanced = QPushButton("Open Channel Studio (advanced)")
        advanced.setObjectName("SecondaryButton")
        advanced.clicked.connect(self._open_studio)

        self._status = QLabel("")
        self._status.setObjectName("PageSubtitle")

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(36, 28, 36, 36)
        layout.setSpacing(12)
        layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._title)
        layout.addWidget(self._hint)
        layout.addWidget(self._tabs, stretch=1)
        row = QHBoxLayout()
        row.addWidget(save)
        row.addWidget(advanced)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(self._status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_channel(self, folder_name: str) -> None:
        self._folder = folder_name
        self.refresh()

    def refresh(self) -> None:
        app = self._app()
        if app is None or not self._folder:
            return
        try:
            channel = app.channels.get_channel(self._folder)
            profile = ChannelProductionProfile.from_channel(channel)
        except (ProjectRootError, OSError, FileNotFoundError, ValueError) as exc:
            self._status.setText(str(exc))
            return

        self._title.setText(f"Channel Settings — {channel.name}")
        self._name.setText(channel.name)
        self._description.setPlainText(profile.description)
        self._intro.setText(profile.intro)
        self._outro.setText(profile.outro)
        self._output.setText(profile.output_folder)
        idx = self._resolution.findData(profile.resolution or "1920x1080")
        self._resolution.setCurrentIndex(max(0, idx))

        self._logo.setText(profile.logo)
        self._banner.setText(profile.banner)
        colors = profile.brand_colors or {}
        self._primary.setText(str(colors.get("primary") or ""))
        self._secondary.setText(str(colors.get("secondary") or ""))
        self._accent.setText(str(colors.get("accent") or ""))

        vp = profile.voice_provider or str(profile.voice.get("provider") or "kokoro")
        vidx = self._voice_provider.findData(vp)
        self._voice_provider.setCurrentIndex(max(0, vidx))
        self._voice_id.setText(str(profile.voice.get("voice_id") or ""))
        self._voice_name.setText(str(profile.voice.get("voice_name") or ""))
        tags = profile.voice.get("style_tags") or []
        self._voice_styles.setText(", ".join(str(t) for t in tags))
        self._voice_speed.setText(str(profile.voice.get("speed") or ""))

        aidx = self._ai_provider.findData(profile.ai_provider or "ollama")
        self._ai_provider.setCurrentIndex(max(0, aidx))
        self._ai_model.setText(profile.ai_model)

        self._image_style.setText(profile.image_style)
        self._prompt_template.setText(profile.prompt_template)
        self._image_prompt.setPlainText(profile.image_prompt)
        self._negative.setPlainText(profile.negative_prompt)

        self._movie_notes.setText(str((profile.movie or {}).get("notes") or ""))
        self._export_notes.setText(str((profile.export or {}).get("notes") or ""))
        self._status.setText("")

    def _save(self) -> None:
        app = self._app()
        if app is None or not self._folder:
            return
        try:
            channel = app.channels.get_channel(self._folder)
            profile = ChannelProductionProfile.from_channel(channel)
        except (ProjectRootError, OSError, FileNotFoundError, ValueError) as exc:
            QMessageBox.warning(self, "Channel Settings", str(exc))
            return

        profile.description = self._description.toPlainText().strip()
        profile.intro = self._intro.text().strip()
        profile.outro = self._outro.text().strip()
        profile.output_folder = self._output.text().strip()
        profile.resolution = str(self._resolution.currentData() or "1920x1080")
        profile.logo = self._logo.text().strip()
        profile.banner = self._banner.text().strip()
        profile.brand_colors = {
            "primary": self._primary.text().strip(),
            "secondary": self._secondary.text().strip(),
            "accent": self._accent.text().strip(),
        }
        profile.voice_provider = str(self._voice_provider.currentData() or "")
        tags = [t.strip() for t in self._voice_styles.text().split(",") if t.strip()]
        voice = dict(profile.voice or {})
        voice["provider"] = profile.voice_provider
        voice["voice_id"] = self._voice_id.text().strip()
        voice["voice_name"] = self._voice_name.text().strip()
        voice["style_tags"] = tags
        speed = self._voice_speed.text().strip()
        if speed:
            try:
                voice["speed"] = float(speed)
            except ValueError:
                pass
        profile.voice = voice
        profile.ai_provider = str(self._ai_provider.currentData() or "ollama")
        profile.ai_model = self._ai_model.text().strip()
        profile.image_style = self._image_style.text().strip()
        profile.prompt_template = self._prompt_template.text().strip()
        profile.image_prompt = self._image_prompt.toPlainText().strip()
        profile.negative_prompt = self._negative.toPlainText().strip()
        movie = dict(profile.movie or {})
        movie["notes"] = self._movie_notes.text().strip()
        profile.movie = movie
        export = dict(profile.export or {})
        export["notes"] = self._export_notes.text().strip()
        profile.export = export

        profile.apply_to_channel(channel)
        try:
            app.channels.save_channel(channel)
        except (ProjectRootError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Channel Settings", str(exc))
            return
        self._status.setText(
            "Saved. New projects will inherit these defaults. "
            "Existing projects keep their snapshots."
        )
        app.show_notification("Channel Settings", f"Saved {channel.name}")

    def _open_studio(self) -> None:
        if self._folder:
            self.channel_studio_requested.emit(self._folder)

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None
