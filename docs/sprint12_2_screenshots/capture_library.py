"""Capture Sprint 12.2 Voice Library stills."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.providers.voice_base import VoiceInfo  # noqa: E402
from app.ui.theme.atlas_theme import apply_theme  # noqa: E402
from app.ui.widgets.voice_library import VoiceLibraryWidget  # noqa: E402

OUT = ROOT / "docs" / "sprint12_2_screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app)

    voices = [
        VoiceInfo("af_bella", "Bella", "en-US", gender="Female", style_tags=("Warm", "Friendly")),
        VoiceInfo("af_heart", "Heart", "en-US", gender="Female", style_tags=("Warm", "Soft")),
        VoiceInfo("af_sarah", "Sarah", "en-US", gender="Female", style_tags=("Warm", "Calm")),
        VoiceInfo("af_nova", "Nova", "en-US", gender="Female", style_tags=("Modern", "Clear")),
        VoiceInfo(
            "am_adam",
            "Adam",
            "en-US",
            gender="Male",
            style_tags=("Clear", "Neutral", "Documentary"),
        ),
        VoiceInfo(
            "am_eric",
            "Eric",
            "en-US",
            gender="Male",
            style_tags=("Energetic", "Modern", "Confident"),
        ),
        VoiceInfo(
            "am_michael",
            "Michael",
            "en-US",
            gender="Male",
            style_tags=("Deep", "Calm", "Documentary", "Authoritative"),
        ),
        VoiceInfo(
            "am_james",
            "James",
            "en-US",
            gender="Male",
            style_tags=("Clear", "Confident"),
        ),
    ]

    host = QWidget()
    host.setObjectName("PageFrame")
    host.setFixedSize(640, 720)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(28, 28, 28, 28)
    title = QLabel("Voice Library")
    title.setObjectName("SectionLabel")
    library = VoiceLibraryWidget()
    library.set_voices(voices, selected_voice_id="am_michael")
    layout.addWidget(title)
    layout.addWidget(library)
    host.show()
    app.processEvents()
    host.grab().save(str(OUT / "voice_library.png"))
    print("wrote", OUT / "voice_library.png")


if __name__ == "__main__":
    main()
