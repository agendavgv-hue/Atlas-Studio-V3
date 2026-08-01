"""AI Channel Creator wizard — NEW channels only (never Hollow Atlas / Mirror Drift)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.atlas_application import AtlasApplication
from app.channels.ai_channel_creator import AIChannelCreator
from app.channels.generated_profile import GeneratedChannelProfile
from app.channels.reference_channels import is_reference_channel
from app.core.project_root import ProjectRootError


class AIChannelCreatorDialog(QDialog):
    """Collect a brief, generate DNA, create a new channel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Channel Creator")
        self.setMinimumWidth(560)
        self._profile: GeneratedChannelProfile | None = None

        title = QLabel("Create a NEW channel with AI Channel DNA")
        title.setObjectName("PageTitle")
        hint = QLabel(
            "Hollow Atlas and Mirror Drift are locked reference channels and "
            "cannot be changed here. This wizard only creates new channels."
        )
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Channel name (e.g. Night Orchard)")
        self._concept = QPlainTextEdit()
        self._concept.setPlaceholderText(
            "Concept / niche — what stories does this channel tell?"
        )
        self._concept.setFixedHeight(90)
        self._tone = QLineEdit()
        self._tone.setPlaceholderText("Tone (e.g. mystical, premium tech, calm nature)")

        form = QFormLayout()
        form.addRow("Name", self._name)
        form.addRow("Concept", self._concept)
        form.addRow("Tone", self._tone)

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("Generated Channel DNA preview appears here.")
        self._preview.setMinimumHeight(180)

        generate = QPushButton("Generate Channel DNA")
        generate.setObjectName("PrimaryButton")
        generate.clicked.connect(self._generate)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create Channel")
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self._buttons.accepted.connect(self._create)
        self._buttons.rejected.connect(self.reject)

        actions = QHBoxLayout()
        actions.addWidget(generate)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(QLabel("Preview"))
        layout.addWidget(self._preview, stretch=1)
        layout.addWidget(self._buttons)

    def created_profile(self) -> GeneratedChannelProfile | None:
        return self._profile

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _generate(self) -> None:
        name = self._name.text().strip()
        concept = self._concept.toPlainText().strip()
        tone = self._tone.text().strip()
        if not name:
            QMessageBox.warning(self, "AI Channel Creator", "Enter a channel name.")
            return
        if is_reference_channel(name):
            QMessageBox.warning(
                self,
                "AI Channel Creator",
                "Hollow Atlas and Mirror Drift are locked reference channels.\n"
                "Choose a different name for a NEW channel.",
            )
            return
        if not concept:
            QMessageBox.warning(
                self, "AI Channel Creator", "Describe the channel concept / niche."
            )
            return

        app = self._app()
        text_provider = None
        if app is not None:
            try:
                text_provider = app.production.resolve_text_provider()
            except Exception:  # noqa: BLE001
                text_provider = None

        creator = AIChannelCreator(text_provider)
        try:
            profile = creator.generate(name=name, concept=concept, tone=tone)
        except ValueError as exc:
            QMessageBox.warning(self, "AI Channel Creator", str(exc))
            return

        self._profile = profile
        self._preview.setPlainText(_preview_text(profile))
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _create(self) -> None:
        app = self._app()
        if app is None or self._profile is None:
            return
        try:
            channel = app.channels.create_channel_from_profile(self._profile)
            app.channels.select_channel(channel.folder_name)
        except (ProjectRootError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "AI Channel Creator", str(exc))
            return
        app.show_notification("Channel Created", channel.name)
        self.accept()


def _preview_text(profile: GeneratedChannelProfile) -> str:
    dna = profile.dna or {}
    colors = dna.get("color_language") if isinstance(dna.get("color_language"), dict) else {}
    lines = [
        f"Name: {profile.name}",
        f"Description: {profile.description}",
        f"Outro: {profile.outro_line}",
        f"Signature: {dna.get('signature', '')}",
        f"Colors: {colors.get('primary', '')} / {colors.get('secondary', '')} / {colors.get('accent', '')}",
        f"Image prompt: {profile.image_prompt[:240]}…",
        f"Negative: {profile.negative_prompt[:160]}…",
    ]
    return "\n\n".join(lines)
