"""Lightweight embedded voice player — Play / Pause / seek / time."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.pipelines.voice_info import format_duration_ms

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
except ImportError:  # pragma: no cover - environment without QtMultimedia
    QAudioOutput = None  # type: ignore[misc, assignment]
    QMediaPlayer = None  # type: ignore[misc, assignment]


class VoicePlayer(QWidget):
    """Minimal narration preview. No waveform / editing."""

    duration_ready = Signal(int)  # milliseconds
    availability_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VoicePlayer")
        self._path: Path | None = None
        self._duration_ms = 0
        self._updating_slider = False
        self._available = False

        self._play = QPushButton("Play")
        self._play.setObjectName("SecondaryButton")
        self._play.clicked.connect(self._toggle_play)
        self._play.setEnabled(False)

        self._slider = QSlider()
        self._slider.setOrientation(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setEnabled(False)
        self._slider.sliderMoved.connect(self._seek)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)

        self._time = QLabel("0:00 / 0:00")
        self._time.setObjectName("PageSubtitle")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self._play)
        row.addWidget(self._slider, stretch=1)
        row.addWidget(self._time)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(row)

        self._player = None
        self._audio = None
        self._slider_dragging = False
        if QMediaPlayer is not None and QAudioOutput is not None:
            self._audio = QAudioOutput(self)
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(self._audio)
            self._player.positionChanged.connect(self._on_position)
            self._player.durationChanged.connect(self._on_duration)
            self._player.playbackStateChanged.connect(self._on_state)
            self._player.errorOccurred.connect(self._on_error)
        else:
            self._time.setText("Audio playback unavailable")

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    def set_source(self, path: Path | None) -> None:
        """Load an audio file, or clear when path is None / missing."""
        self._path = path if path is not None and path.is_file() else None
        self._duration_ms = 0
        self._slider.setValue(0)
        self._slider.setRange(0, 0)
        self._time.setText("0:00 / 0:00")

        if self._player is None:
            self._set_available(False)
            return

        self._player.stop()
        if self._path is None:
            self._player.setSource(QUrl())
            self._play.setEnabled(False)
            self._slider.setEnabled(False)
            self._play.setText("Play")
            self._set_available(False)
            return

        self._player.setSource(QUrl.fromLocalFile(str(self._path.resolve())))
        self._play.setEnabled(True)
        self._slider.setEnabled(True)
        self._play.setText("Play")
        self._set_available(True)

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()
        self._play.setText("Play")

    def _set_available(self, available: bool) -> None:
        if self._available == available:
            return
        self._available = available
        self.availability_changed.emit(available)

    def _toggle_play(self) -> None:
        if self._player is None or self._path is None:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    @Slot(int)
    def _on_position(self, position: int) -> None:
        if self._slider_dragging or self._updating_slider:
            return
        self._updating_slider = True
        self._slider.setValue(position)
        self._updating_slider = False
        self._update_time_label(position)

    @Slot(int)
    def _on_duration(self, duration: int) -> None:
        self._duration_ms = max(0, int(duration))
        self._slider.setRange(0, self._duration_ms)
        self._update_time_label(self._slider.value())
        if self._duration_ms > 0:
            self.duration_ready.emit(self._duration_ms)

    @Slot(object)
    def _on_state(self, state) -> None:
        if self._player is None:
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play.setText("Pause")
        else:
            self._play.setText("Play")

    def _on_error(self, *_args) -> None:
        self._play.setEnabled(False)
        self._slider.setEnabled(False)
        self._time.setText("Unable to play this file")
        self._set_available(False)

    def _seek(self, position: int) -> None:
        if self._player is not None:
            self._player.setPosition(position)
        self._update_time_label(position)

    def _on_slider_pressed(self) -> None:
        self._slider_dragging = True

    def _on_slider_released(self) -> None:
        self._slider_dragging = False
        if self._player is not None:
            self._player.setPosition(self._slider.value())
        self._update_time_label(self._slider.value())

    def _update_time_label(self, position_ms: int) -> None:
        current = format_duration_ms(position_ms)
        total = format_duration_ms(self._duration_ms)
        self._time.setText(f"{current} / {total}")
