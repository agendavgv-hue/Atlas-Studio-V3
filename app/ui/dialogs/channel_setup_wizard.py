"""Channel Setup Wizard — collect production defaults once per channel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.atlas_application import AtlasApplication
from app.channels.channel_paths import ChannelPaths
from app.channels.models import Channel
from app.channels.reference_channels import is_reference_channel
from app.core.project_root import ProjectRootError, require_project_root


class ChannelSetupWizard(QDialog):
    """Ask once for channel production defaults; editable later in Channel Studio / Settings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Channel")
        self.setMinimumWidth(520)
        self._created: Channel | None = None

        title = QLabel("Set up your channel")
        title.setObjectName("PageTitle")
        hint = QLabel(
            "Configure once. Production will use these defaults automatically — "
            "you can change them later in Channel Studio or Settings."
        )
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Channel name")

        self._primary = QLineEdit()
        self._primary.setPlaceholderText("#1A1A1A")
        self._secondary = QLineEdit()
        self._secondary.setPlaceholderText("#C9A227")
        self._accent = QLineEdit()
        self._accent.setPlaceholderText("#F5F0E6")

        self._logo = QLineEdit()
        self._logo.setPlaceholderText("Optional path to logo image")
        logo_browse = QPushButton("Browse…")
        logo_browse.clicked.connect(self._browse_logo)
        logo_row = QHBoxLayout()
        logo_row.addWidget(self._logo, stretch=1)
        logo_row.addWidget(logo_browse)

        self._voice = QLineEdit()
        self._voice.setPlaceholderText("e.g. Deep, Calm, Documentary")

        self._ai_provider = QComboBox()
        self._ai_provider.addItem("Ollama (local)", "ollama")
        self._ai_provider.addItem("Gemini", "gemini")
        self._ai_provider.addItem("OpenAI", "openai")
        self._ai_provider.addItem("Claude", "anthropic")

        self._ai_model = QLineEdit()
        self._ai_model.setPlaceholderText("Preferred model id (optional)")

        self._image_style = QLineEdit()
        self._image_style.setPlaceholderText("e.g. cinematic documentary, warm gold")

        self._prompt_template = QLineEdit()
        self._prompt_template.setPlaceholderText("Optional house style keywords")

        self._output_folder = QLineEdit()
        self._output_folder.setPlaceholderText("Leave blank for Project Root default")
        out_browse = QPushButton("Browse…")
        out_browse.clicked.connect(self._browse_output)
        out_row = QHBoxLayout()
        out_row.addWidget(self._output_folder, stretch=1)
        out_row.addWidget(out_browse)

        self._resolution = QComboBox()
        self._resolution.addItem("1920 × 1080 (YouTube)", "1920x1080")
        self._resolution.addItem("1280 × 720", "1280x720")
        self._resolution.addItem("3840 × 2160 (4K)", "3840x2160")

        form = QFormLayout()
        form.addRow("Channel Name", self._name)
        form.addRow("Primary Color", self._primary)
        form.addRow("Secondary Color", self._secondary)
        form.addRow("Accent Color", self._accent)
        form.addRow("Logo", logo_row)
        form.addRow("Voice Style", self._voice)
        form.addRow("AI Provider", self._ai_provider)
        form.addRow("Preferred AI Model", self._ai_model)
        form.addRow("Image Style", self._image_style)
        form.addRow("Prompt Template", self._prompt_template)
        form.addRow("Output Folder", out_row)
        form.addRow("Default Resolution", self._resolution)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create Channel")
        buttons.accepted.connect(self._create)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def created_channel(self) -> Channel | None:
        return self._created

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _browse_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Logo",
            "",
            "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
        if path:
            self._logo.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Output Folder")
        if path:
            self._output_folder.setText(path)

    def _create(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "New Channel", "Enter a channel name.")
            return
        if is_reference_channel(name):
            QMessageBox.warning(
                self,
                "New Channel",
                "Hollow Atlas and Mirror Drift are locked reference channels.\n"
                "Choose a different name.",
            )
            return

        app = self._app()
        if app is None:
            return
        try:
            channel = app.channels.create_channel(name)
        except (ProjectRootError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "New Channel", str(exc))
            return

        studio = {
            "brand_colors": {
                "primary": self._primary.text().strip(),
                "secondary": self._secondary.text().strip(),
                "accent": self._accent.text().strip(),
            },
            "ai_provider": str(self._ai_provider.currentData() or "ollama"),
            "ai_model": self._ai_model.text().strip(),
            "image_style": self._image_style.text().strip(),
            "prompt_template": self._prompt_template.text().strip(),
            "output_folder": self._output_folder.text().strip(),
            "resolution": str(self._resolution.currentData() or "1920x1080"),
            "voice_style": self._voice.text().strip(),
        }
        channel.studio = studio

        logo_src = self._logo.text().strip()
        if logo_src:
            try:
                channel.logo = self._copy_logo(app, channel.folder_name, logo_src)
            except OSError as exc:
                QMessageBox.warning(self, "New Channel", f"Could not copy logo: {exc}")

        voice_style = self._voice.text().strip()
        if voice_style:
            tags = [t.strip() for t in voice_style.split(",") if t.strip()]
            voice = dict(channel.voice or {})
            if tags:
                voice["style_tags"] = tags
            channel.voice = voice

        try:
            app.channels.save_channel(channel)
            app.channels.select_channel(channel.folder_name)
        except (ProjectRootError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "New Channel", str(exc))
            return

        self._created = channel
        app.show_notification("Channel Created", channel.name)
        self.accept()

    def _copy_logo(self, app: AtlasApplication, folder_name: str, source: str) -> str:
        src = Path(source)
        if not src.is_file():
            raise OSError(f"Logo file not found: {source}")
        root = require_project_root(app.config.project_root)
        paths = ChannelPaths(app.storage, root)
        branding = paths.library_dir(folder_name) / "branding"
        branding.mkdir(parents=True, exist_ok=True)
        dest = branding / f"logo{src.suffix.lower() or '.png'}"
        dest.write_bytes(src.read_bytes())
        return f"branding/{dest.name}"
