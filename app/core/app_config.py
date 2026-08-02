"""Application configuration persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from app.core.forge_settings import ForgeSettings
from app.core.movie_settings import MovieSettings
from app.core.voice_settings import VoiceSettings
from app.ai.settings import AIOrchestratorSettings


CONFIG_FILENAME = "config.json"


def default_data_root() -> Path:
    """Atlas Studio data root (parent of the ``app`` package)."""
    return Path(__file__).resolve().parents[2]


def bootstrap_config_path() -> Path:
    """Platform user-config location for Atlas Studio settings."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return Path(base) / CONFIG_FILENAME


@dataclass
class AppConfig:
    """Persisted application settings.

    Bootstrap config lives in the platform user-config directory so roots
    can be changed safely.
    """

    data_root: Path
    project_root: Path | None = None
    text_provider: str | None = None
    gemini_api_key: str = ""
    gemini_model: str = ""
    image_provider: str | None = None
    forge: ForgeSettings = field(default_factory=ForgeSettings)
    voice_provider: str | None = None
    voice: VoiceSettings = field(default_factory=VoiceSettings)
    movie: MovieSettings = field(default_factory=MovieSettings)
    ai: AIOrchestratorSettings = field(default_factory=AIOrchestratorSettings.defaults)

    @classmethod
    def load(cls, default_root: Path | None = None) -> AppConfig:
        root_fallback = (default_root or default_data_root()).resolve()
        path = bootstrap_config_path()
        if not path.is_file():
            return cls(data_root=root_fallback)

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(data_root=root_fallback)

        stored = raw.get("data_root")
        data_root = (
            Path(stored).expanduser().resolve()
            if stored and isinstance(stored, str)
            else root_fallback
        )

        project_raw = raw.get("project_root")
        project_root: Path | None = None
        if project_raw and isinstance(project_raw, str):
            project_root = Path(project_raw).expanduser().resolve()

        text_provider = raw.get("text_provider")
        if text_provider is not None and not isinstance(text_provider, str):
            text_provider = None

        gemini_api_key = raw.get("gemini_api_key")
        if not isinstance(gemini_api_key, str):
            gemini_api_key = ""

        gemini_model = raw.get("gemini_model")
        if not isinstance(gemini_model, str):
            gemini_model = ""
        else:
            gemini_model = gemini_model.strip()

        image_provider = raw.get("image_provider")
        if image_provider is not None and not isinstance(image_provider, str):
            image_provider = None

        forge_raw = raw.get("forge")
        forge = ForgeSettings.from_mapping(forge_raw if isinstance(forge_raw, dict) else None)

        voice_provider = raw.get("voice_provider")
        if voice_provider is not None and not isinstance(voice_provider, str):
            voice_provider = None

        voice_raw = raw.get("voice")
        voice = VoiceSettings.from_mapping(voice_raw if isinstance(voice_raw, dict) else None)

        movie_raw = raw.get("movie")
        movie = MovieSettings.from_mapping(movie_raw if isinstance(movie_raw, dict) else None)

        ai_raw = raw.get("ai")
        ai = AIOrchestratorSettings.from_mapping(ai_raw if isinstance(ai_raw, dict) else None)

        return cls(
            data_root=data_root,
            project_root=project_root,
            text_provider=text_provider,
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
            image_provider=image_provider,
            forge=forge,
            voice_provider=voice_provider,
            voice=voice,
            movie=movie,
            ai=ai,
        )

    def save(self) -> None:
        path = bootstrap_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "data_root": str(self.data_root.resolve()),
            "project_root": (
                str(self.project_root.resolve()) if self.project_root is not None else None
            ),
            "text_provider": self.text_provider,
            "gemini_api_key": self.gemini_api_key,
            "gemini_model": self.gemini_model,
            "image_provider": self.image_provider,
            "forge": self.forge.to_dict(),
            "voice_provider": self.voice_provider,
            "voice": self.voice.to_dict(),
            "movie": self.movie.to_dict(),
            "ai": self.ai.to_dict(),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
