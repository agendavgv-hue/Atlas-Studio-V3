"""Channels page — list, create, select, and channel narrator preferences."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.channels.voice_preferences import (
    ChannelVoicePreferences,
    resolve_channel_voice_preferences,
)
from app.core.project_root import ProjectRootError, is_project_root_configured
from app.core.storage_paths import StoragePaths
from app.core.voice_settings import VoiceSettings
from app.providers.elevenlabs import ElevenLabsVoiceProvider
from app.providers.kokoro import KOKORO_PROVIDER_ID, KokoroProvider
from app.providers.voice_base import VoiceInfo
from app.providers.voice_metadata import select_closest_voice
from app.ui.widgets.empty_state import EmptyState
from app.ui.widgets.voice_library import VoiceLibraryWidget


class ChannelsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")
        self._current_folder: str | None = None

        title = QLabel("Channels")
        title.setObjectName("PageTitle")

        self._subtitle = QLabel("Select a Project Root in Settings to load channels.")
        self._subtitle.setObjectName("PageSubtitle")

        self._list = QListWidget()
        self._list.setObjectName("ChannelList")
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        self._empty = EmptyState()

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("New channel name")
        self._name_input.returnPressed.connect(self._create_channel)

        create_button = QPushButton("Create Channel")
        create_button.setObjectName("PrimaryButton")
        create_button.clicked.connect(self._create_channel)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)

        create_row = QHBoxLayout()
        create_row.addWidget(self._name_input, stretch=1)
        create_row.addWidget(create_button)
        create_row.addWidget(refresh_button)

        self._voice_title = QLabel("Channel Narrator")
        self._voice_title.setObjectName("SectionLabel")
        self._voice_hint = QLabel(
            "Choose the preferred narrator for this channel. "
            "Projects under the channel load these defaults automatically."
        )
        self._voice_hint.setObjectName("PageSubtitle")
        self._voice_hint.setWordWrap(True)

        self._voice_gender = QLineEdit()
        self._voice_gender.setPlaceholderText("Male / Female")
        self._voice_styles = QLineEdit()
        self._voice_styles.setPlaceholderText("Deep, Calm, Documentary")
        self._voice_language = QLineEdit()
        self._voice_language.setPlaceholderText("en-US")
        self._voice_speed = QLineEdit()
        self._voice_speed.setPlaceholderText("1.0")
        self._voice_provider = QLineEdit()
        self._voice_provider.setPlaceholderText("kokoro")

        prefs_form = QFormLayout()
        prefs_form.addRow("Provider", self._voice_provider)
        prefs_form.addRow("Gender", self._voice_gender)
        prefs_form.addRow("Style tags", self._voice_styles)
        prefs_form.addRow("Language", self._voice_language)
        prefs_form.addRow("Speed", self._voice_speed)

        self._voice_library = VoiceLibraryWidget()
        self._voice_library.voice_selected.connect(self._on_channel_voice_selected)

        auto_pick = QPushButton("Auto-Pick Closest Voice")
        auto_pick.clicked.connect(self._auto_pick_voice)
        save_voice = QPushButton("Save Channel Voice")
        save_voice.setObjectName("PrimaryButton")
        save_voice.clicked.connect(self._save_channel_voice)
        voice_actions = QHBoxLayout()
        voice_actions.addWidget(auto_pick)
        voice_actions.addWidget(save_voice)
        voice_actions.addStretch()

        self._voice_panel = QWidget()
        voice_layout = QVBoxLayout(self._voice_panel)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(8)
        voice_layout.addWidget(self._voice_title)
        voice_layout.addWidget(self._voice_hint)
        voice_layout.addLayout(prefs_form)
        voice_layout.addWidget(self._voice_library, stretch=1)
        voice_layout.addLayout(voice_actions)
        self._voice_panel.setEnabled(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self._list, stretch=1)
        left_layout.addWidget(self._empty, stretch=1)
        left_layout.addLayout(create_row)
        self._empty.hide()

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left)
        splitter.addWidget(self._voice_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self._status = QLabel("")
        self._status.setObjectName("PageSubtitle")
        self._voice_library.status_message.connect(self._status.setText)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(self._subtitle)
        layout.addWidget(splitter, stretch=1)
        layout.addWidget(self._status)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def _focus_create(self) -> None:
        self._name_input.setFocus()

    def _go_settings(self) -> None:
        window = self.window()
        show = getattr(window, "_show_page", None)
        if callable(show):
            show("settings")

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _show_list(self, visible: bool) -> None:
        self._list.setVisible(visible)
        self._empty.setVisible(not visible)

    def refresh(self) -> None:
        app = self._app()
        self._list.clear()
        if app is None:
            self._subtitle.setText("Application is not ready.")
            self._show_list(False)
            self._voice_panel.setEnabled(False)
            return

        if not is_project_root_configured(app.config.project_root):
            self._subtitle.setText("Project Root is not set.")
            self._status.setText("")
            self._empty.configure(
                "No Project Root",
                "Choose your YouTube library folder in Settings to discover channels.",
                "Open Settings",
                self._go_settings,
            )
            self._show_list(False)
            self._voice_panel.setEnabled(False)
            return

        try:
            channels = app.channels.list_channels()
        except ProjectRootError as exc:
            self._subtitle.setText(str(exc))
            self._status.setText("")
            self._show_list(False)
            self._voice_panel.setEnabled(False)
            return

        self._subtitle.setText(
            f"Project Root: {app.config.project_root}  ·  {len(channels)} channel(s)"
        )
        active = app.channels.active_channel_name
        for channel in channels:
            item = QListWidgetItem(channel.name)
            item.setData(Qt.ItemDataRole.UserRole, channel.folder_name)
            self._list.addItem(item)
            if active and channel.folder_name == active:
                item.setSelected(True)

        if not channels:
            self._empty.configure(
                "No Channels yet",
                "Create a channel or add a folder inside your Project Root.",
                "Create Channel",
                self._focus_create,
            )
            self._list.hide()
            self._empty.show()
            self._status.setText("")
            self._voice_panel.setEnabled(False)
            return

        self._show_list(True)
        if active:
            self._status.setText(f"Active channel: {active}")
        else:
            self._status.setText("Select a channel to edit its narrator.")

    def _create_channel(self) -> None:
        app = self._app()
        if app is None:
            return
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Atlas Studio", "Enter a channel name.")
            return
        try:
            channel = app.channels.create_channel(name)
            app.channels.select_channel(channel.folder_name)
        except (ProjectRootError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._name_input.clear()
        self.refresh()
        app.show_notification("Channel Created", channel.name)

    def _on_selection_changed(self) -> None:
        app = self._app()
        if app is None:
            return
        items = self._list.selectedItems()
        if not items:
            self._voice_panel.setEnabled(False)
            self._current_folder = None
            return
        folder_name = items[0].data(Qt.ItemDataRole.UserRole)
        if not folder_name:
            return
        try:
            channel = app.channels.select_channel(str(folder_name))
        except (ProjectRootError, FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        self._current_folder = channel.folder_name
        self._status.setText(f"Active channel: {folder_name}")
        self._load_channel_voice(channel.name, channel.voice)

    def _load_channel_voice(self, channel_name: str, stored: dict) -> None:
        self._voice_panel.setEnabled(True)
        provider = self._build_provider()
        voices: list[VoiceInfo] = []
        if provider is not None:
            self._voice_library.set_provider(provider)
            try:
                voices = provider.list_voices()
            except Exception:  # noqa: BLE001
                voices = []
        prefs = resolve_channel_voice_preferences(
            channel_name, stored, voices=voices or None
        )
        self._voice_provider.setText(prefs.provider or KOKORO_PROVIDER_ID)
        self._voice_gender.setText(prefs.gender)
        self._voice_styles.setText(", ".join(prefs.style_tags))
        self._voice_language.setText(prefs.language)
        self._voice_speed.setText(str(prefs.speed))
        self._voice_library.set_voices(
            voices,
            selected_voice_id=prefs.voice_id,
            gender=prefs.gender,
            style_tags=prefs.style_tags,
            language=prefs.language,
        )
        selected = self._voice_library.selected_voice()
        if selected is not None and (
            selected.voice_id != prefs.voice_id or self._voice_library.last_warning
        ):
            # Persist closest match so the channel remembers it next launch.
            prefs.bind_voice(selected)
            prefs.gender = self._voice_gender.text().strip() or prefs.gender
            prefs.style_tags = [
                part.strip()
                for part in self._voice_styles.text().split(",")
                if part.strip()
            ] or prefs.style_tags
            channel_folder = self._current_folder
            app = self._app()
            if app is not None and channel_folder:
                try:
                    channel = app.channels.get_channel(channel_folder)
                    channel.voice = prefs.to_dict()
                    app.channels.save_channel(channel)
                except Exception:  # noqa: BLE001
                    pass
        if not voices:
            self._status.setText("No voices available.")
        elif self._voice_library.last_warning:
            pass
        elif prefs.voice_name or (selected and selected.name):
            name = (selected.name if selected else None) or prefs.voice_name
            gender = f" · {prefs.gender}" if prefs.gender else ""
            self._status.setText(f"{channel_name} narrator: {name}{gender}")

    def _read_channel_prefs(self) -> ChannelVoicePreferences:
        styles = [
            part.strip()
            for part in self._voice_styles.text().split(",")
            if part.strip()
        ]
        selected = self._voice_library.selected_voice()
        try:
            speed = float(self._voice_speed.text() or 1.0)
        except ValueError as exc:
            raise ValueError("Speed must be a number.") from exc
        return ChannelVoicePreferences(
            provider=self._voice_provider.text().strip() or KOKORO_PROVIDER_ID,
            voice_id=selected.voice_id if selected else "",
            voice_name=selected.name if selected else "",
            speed=speed,
            language=self._voice_language.text().strip() or "en-US",
            gender=self._voice_gender.text().strip(),
            style_tags=styles,
        )

    def _on_channel_voice_selected(self, voice: object) -> None:
        if isinstance(voice, VoiceInfo) and voice.language:
            self._voice_language.setText(voice.language)
        if isinstance(voice, VoiceInfo) and voice.gender:
            self._voice_gender.setText(voice.gender)
        if isinstance(voice, VoiceInfo):
            self._auto_persist_channel_voice(voice)

    def _auto_persist_channel_voice(self, voice: VoiceInfo) -> None:
        """Remember the channel narrator across app restarts."""
        app = self._app()
        if app is None or not self._current_folder:
            return
        try:
            prefs = self._read_channel_prefs()
        except ValueError:
            return
        prefs.bind_voice(voice)
        try:
            channel = app.channels.get_channel(self._current_folder)
            if channel.voice.get("voice_id") == prefs.voice_id:
                return
            channel.voice = prefs.to_dict()
            app.channels.save_channel(channel)
        except Exception:  # noqa: BLE001
            return

    def _auto_pick_voice(self) -> None:
        try:
            prefs = self._read_channel_prefs()
        except ValueError as exc:
            self._status.setText(str(exc))
            return
        voices = list(self._voice_library.voices)
        if not voices:
            self._status.setText("No voices available.")
            return
        match = select_closest_voice(
            voices,
            gender=prefs.gender,
            style_tags=prefs.style_tags,
            language=prefs.language,
        )
        if match is None:
            self._status.setText("No voices available.")
            return
        self._voice_library.set_voices(voices, selected_voice_id=match.voice_id)
        self._status.setText(f"Closest match: {match.name}")

    def _save_channel_voice(self) -> None:
        app = self._app()
        if app is None or not self._current_folder:
            return
        try:
            prefs = self._read_channel_prefs()
        except ValueError as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        if not prefs.voice_id:
            self._status.setText("Select a voice in the Voice Library first.")
            return
        try:
            channel = app.channels.get_channel(self._current_folder)
            channel.voice = prefs.to_dict()
            app.channels.save_channel(channel)
        except (ProjectRootError, FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            return
        label = prefs.voice_name or prefs.voice_id
        self._status.setText(f"Saved narrator for {channel.name}: {label}")
        app.show_notification("Channel Voice Saved", f"{channel.name} · {label}")

    def _build_provider(self):
        app = self._app()
        if app is None:
            return None
        provider_id = (
            self._voice_provider.text().strip()
            or app.config.voice_provider
            or KOKORO_PROVIDER_ID
        ).casefold()
        settings = VoiceSettings.from_mapping(app.config.voice.to_dict())
        model_dir = StoragePaths(app.config.data_root).cache / "kokoro"
        if provider_id == "elevenlabs":
            try:
                return ElevenLabsVoiceProvider(settings)
            except Exception:  # noqa: BLE001
                return KokoroProvider(settings, model_dir=model_dir)
        return KokoroProvider(settings, model_dir=model_dir)
