"""Provider-agnostic Voice Library — searchable catalogue with preview."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.providers.errors import ProviderError
from app.providers.voice_base import VoiceInfo, VoiceProvider, VoiceSynthesisRequest
from app.providers.voice_metadata import resolve_available_voice
from app.ui.widgets.voice_player import VoicePlayer

PreviewSynthesizer = Callable[[VoiceInfo], bytes]


class VoiceLibraryWidget(QWidget):
    """Searchable voice catalogue grouped by gender.

    Works for any provider that returns rich ``VoiceInfo`` rows.
    """

    voice_selected = Signal(object)  # VoiceInfo
    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VoiceLibrary")
        self._voices: list[VoiceInfo] = []
        self._selected_id = ""
        self._provider: VoiceProvider | None = None
        self._rows: list[QWidget] = []
        self._last_warning = ""
        self._empty_reason = ""

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search voices…")
        self._search.textChanged.connect(self._rebuild)

        self._empty = QLabel("No voices available.")
        self._empty.setObjectName("PageSubtitle")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("VoiceLibraryScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self._list_host)
        scroll.setMinimumHeight(220)

        self._selection = QLabel("No voice selected")
        self._selection.setObjectName("PageSubtitle")
        self._selection.setWordWrap(True)

        self._warning = QLabel("")
        self._warning.setObjectName("VoiceLibraryWarning")
        self._warning.setWordWrap(True)
        self._warning.hide()

        self._player = VoicePlayer()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._search)
        layout.addWidget(scroll, stretch=1)
        layout.addWidget(self._empty)
        layout.addWidget(self._selection)
        layout.addWidget(self._warning)
        layout.addWidget(self._player)
        self._empty.hide()

    @property
    def selected_voice_id(self) -> str:
        return self._selected_id

    @property
    def voices(self) -> list[VoiceInfo]:
        return list(self._voices)

    def selected_voice(self) -> VoiceInfo | None:
        for voice in self._voices:
            if voice.voice_id == self._selected_id:
                return voice
        return None

    @property
    def last_warning(self) -> str:
        return self._last_warning

    def set_provider(self, provider: VoiceProvider | None) -> None:
        self._provider = provider

    def set_voices(
        self,
        voices: list[VoiceInfo],
        *,
        selected_voice_id: str = "",
        gender: str = "",
        style_tags: tuple[str, ...] | list[str] = (),
        language: str = "",
        channel_language: str = "",
        empty_message: str = "",
    ) -> None:
        from app.channels.language import voice_matches_language

        catalogue = list(voices)
        if channel_language:
            filtered = [
                voice
                for voice in catalogue
                if voice_matches_language(voice.language, channel_language)
            ]
            # Prefer language matches, but never hide the full catalogue when
            # the provider has voices (Kokoro is English-only today).
            if filtered:
                catalogue = filtered
        self._voices = catalogue
        self._empty_reason = (empty_message or "").strip()
        preferred = selected_voice_id or self._selected_id
        resolved, warning = resolve_available_voice(
            self._voices,
            preferred_voice_id=preferred,
            gender=gender,
            style_tags=style_tags,
            language=language,
        )
        self._selected_id = resolved.voice_id if resolved is not None else ""
        self._last_warning = warning
        self._rebuild()
        if resolved is not None:
            self._selection.setText(_selection_label(resolved))
            if warning:
                self._warning.setText(warning)
                self._warning.show()
                self.status_message.emit(warning)
            else:
                self._warning.hide()
                self._warning.clear()
            self.voice_selected.emit(resolved)
        else:
            self._selection.setText("No voice selected")
            reason = self._empty_reason or warning
            if reason:
                self._warning.setText(reason)
                self._warning.show()
                self.status_message.emit(reason)
            else:
                self._warning.hide()
                self._warning.clear()

    def clear(self) -> None:
        self.set_voices([])

    def _filtered(self) -> list[VoiceInfo]:
        query = self._search.text().strip().casefold()
        if not query:
            return list(self._voices)
        results: list[VoiceInfo] = []
        for voice in self._voices:
            haystack = " ".join(
                [
                    voice.name,
                    voice.gender,
                    voice.language,
                    voice.accent,
                    voice.age,
                    " ".join(voice.style_tags),
                    voice.description,
                    voice.voice_id,
                ]
            ).casefold()
            if query in haystack:
                results.append(voice)
        return results

    def _rebuild(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()

        filtered = self._filtered()
        if not filtered:
            self._empty.setText(
                self._empty_reason
                or (
                    "No voices available."
                    if not self._voices
                    else "No voices match your search."
                )
            )
            self._empty.show()
            self._list_layout.addStretch(1)
            return

        self._empty.hide()
        groups: dict[str, list[VoiceInfo]] = {}
        for voice in filtered:
            key = voice.gender.strip() or "Other"
            groups.setdefault(key, []).append(voice)

        preferred_order = ("Female", "Male", "Neutral", "Other")
        ordered_keys = [key for key in preferred_order if key in groups]
        ordered_keys.extend(sorted(k for k in groups if k not in preferred_order))

        for group_name in ordered_keys:
            header = QLabel(group_name)
            header.setObjectName("SectionLabel")
            self._list_layout.addWidget(header)
            for voice in groups[group_name]:
                row = self._make_row(voice)
                self._list_layout.addWidget(row)
                self._rows.append(row)
        self._list_layout.addStretch(1)

    def _make_row(self, voice: VoiceInfo) -> QWidget:
        frame = QFrame()
        frame.setObjectName("VoiceLibraryRow")
        frame.setProperty("selected", voice.voice_id == self._selected_id)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        name = QLabel(voice.name)
        name.setObjectName("VoiceLibraryName")
        meta_parts = [part for part in (voice.gender, voice.language, voice.accent) if part]
        if voice.style_tags:
            meta_parts.append(" · ".join(voice.style_tags[:3]))
        meta = QLabel("  ·  ".join(meta_parts) if meta_parts else voice.voice_id)
        meta.setObjectName("PageSubtitle")
        meta.setWordWrap(True)
        text_col.addWidget(name)
        text_col.addWidget(meta)

        preview = QPushButton("▶ Preview")
        preview.setObjectName("SecondaryButton")
        preview.clicked.connect(lambda *_a, v=voice: self._preview(v))

        select = QPushButton("Select")
        select.setObjectName("PrimaryButton" if voice.voice_id == self._selected_id else "SecondaryButton")
        select.clicked.connect(lambda *_a, v=voice: self._select(v))

        layout.addLayout(text_col, stretch=1)
        layout.addWidget(preview)
        layout.addWidget(select)
        return frame

    def _select(self, voice: VoiceInfo) -> None:
        self._selected_id = voice.voice_id
        self._selection.setText(_selection_label(voice))
        self.voice_selected.emit(voice)
        self._rebuild()

    def _preview(self, voice: VoiceInfo) -> None:
        if self._provider is None:
            self.status_message.emit("No voice provider is ready for preview.")
            return
        voice_id = (voice.voice_id or "").strip()
        if not voice_id:
            # Same provider-facing message Piper raises for Generate Voice.
            if (self._provider.provider_id or "").casefold() == "piper":
                self.status_message.emit("No Piper voice selected.")
            else:
                self.status_message.emit("No voice selected.")
            return
        sample = (
            voice.sample_text.strip()
            or "Welcome to Mirror Drift, where tomorrow begins today."
        )
        self.status_message.emit(f"Generating preview for {voice.name}…")
        from app.voice.generator import synthesize_with_provider

        try:
            response = synthesize_with_provider(
                self._provider,
                VoiceSynthesisRequest(
                    text=sample,
                    voice_id=voice_id,
                    language=voice.language,
                    output_format="wav",
                ),
            )
        except ProviderError as exc:
            self.status_message.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self.status_message.emit(f"Preview failed: {exc}")
            return

        suffix = ".wav"
        content = (response.content_type or "").casefold()
        if "mpeg" in content or "mp3" in content:
            suffix = ".mp3"
        self._player.play_bytes(response.audio_bytes, suffix=suffix)
        self.status_message.emit(f"Playing preview — {voice.name}")
        self._select(voice)


def _selection_label(voice: VoiceInfo) -> str:
    parts = [voice.name]
    if voice.gender:
        parts.append(voice.gender)
    if voice.language:
        parts.append(voice.language)
    if voice.style_tags:
        parts.append(voice.style_tags[0])
    return "  ·  ".join(parts)
