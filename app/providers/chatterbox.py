"""Chatterbox voice provider — local Resemble AI TTS behind VoiceProvider ABC.

Uses the official ``chatterbox-tts`` package. Voice catalogue is discovered
from the package (``get_supported_languages``) plus optional reference clips
under ``voices/chatterbox/``. Voice Pipeline / Service / Generator stay
provider-agnostic.
"""

from __future__ import annotations

import io
import logging
import time
import wave
from pathlib import Path
from typing import Any

from app.core.voice_settings import VoiceSettings
from app.providers.errors import ProviderError
from app.providers.voice_base import (
    VoiceInfo,
    VoiceProvider,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)
from app.providers.voice_metadata import display_name_from_id

logger = logging.getLogger(__name__)

CHATTERBOX_PROVIDER_ID = "chatterbox"
CHATTERBOX_PROVIDER_LABEL = "Chatterbox (Local)"
CHATTERBOX_MODEL_ID = "chatterbox"
DEFAULT_VOICE_ID = "default"

CHATTERBOX_UNAVAILABLE_MESSAGE = (
    "Chatterbox is not installed or not ready. "
    "Install with: pip install chatterbox-tts "
    "(or pip install -r requirements-voice-local.txt). "
    "First generation downloads model weights into the Atlas AI Models folder."
)

_REF_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
_DEFAULT_SAMPLE_TEXT = (
    "Atlas Studio generates premium narration with local Chatterbox voices."
)


class ChatterboxVoiceProvider(VoiceProvider):
    """Local Chatterbox TTS. Returns WAV bytes. Catalogue = package discovery."""

    def __init__(
        self,
        settings: VoiceSettings,
        *,
        voices_dir: Path | None = None,
    ) -> None:
        self._settings = settings
        self._voices_dir = (
            voices_dir.expanduser().resolve()
            if voices_dir is not None
            else (Path.cwd() / "voices" / "chatterbox").resolve()
        )
        self._voices_dir.mkdir(parents=True, exist_ok=True)
        self._engine: Any = None
        self._engine_kind: str = ""
        self._device: str = ""

    @property
    def provider_id(self) -> str:
        return CHATTERBOX_PROVIDER_ID

    @property
    def settings(self) -> VoiceSettings:
        return self._settings

    @property
    def model_dir(self) -> Path:
        """Reference-clip library folder (shown in discovery UI)."""
        return self._voices_dir

    @property
    def voices_dir(self) -> Path:
        return self._voices_dir

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        text = (request.text or "").strip()
        if not text:
            raise ProviderError("Script text is empty — nothing to synthesize.")

        request_voice = _clean_id(request.voice_id)
        settings_voice = _clean_id(self._settings.voice_id)
        # Ignore leftover Kokoro defaults when the request did not pick a voice.
        if settings_voice in {"af_heart", "am_adam"} and not request_voice:
            settings_voice = ""
        voice_id = request_voice or settings_voice or DEFAULT_VOICE_ID

        language = (
            request.language or self._settings.language or ""
        ).strip()
        model = (request.model or self._settings.model or CHATTERBOX_MODEL_ID).strip()
        reference = _resolve_reference_path(
            request_path=getattr(request, "reference_audio_path", "") or "",
            settings_path=getattr(self._settings, "reference_audio_path", "") or "",
            voice_id=voice_id,
            voices_dir=self._voices_dir,
        )

        available = {item.voice_id: item for item in self.list_voices()}
        if voice_id not in available and voice_id != DEFAULT_VOICE_ID:
            # Allow DEFAULT even if list failed partially; otherwise clear error.
            if not available:
                raise ProviderError("No Chatterbox voice selected.")
            raise ProviderError(
                f"Chatterbox voice '{voice_id}' was not found. "
                f"Available: {', '.join(sorted(available))}."
            )

        language_id = _language_id_for(voice_id=voice_id, language=language)
        self.validate_ready()

        logger.info(
            "Chatterbox synthesis | provider=%s | voice=%s | model=%s | "
            "language=%s | language_id=%s | reference=%s | output=wav-bytes",
            self.provider_id,
            voice_id,
            model,
            language or "(unset)",
            language_id or "(default)",
            reference or "(none)",
        )

        started = time.perf_counter()
        try:
            wav_bytes, command = self._synthesize_wav(
                text,
                voice_id=voice_id,
                language_id=language_id,
                reference_path=reference,
            )
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Chatterbox synthesis failed: {exc}") from exc

        if not wav_bytes:
            raise ProviderError("Chatterbox produced an empty WAV payload.")

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "Chatterbox synthesis ok | command=%s | bytes=%s | ms=%s",
            command,
            len(wav_bytes),
            elapsed_ms,
        )
        return VoiceSynthesisResponse(
            audio_bytes=wav_bytes,
            content_type="audio/wav",
            model=model or CHATTERBOX_MODEL_ID,
            voice_id=voice_id,
            generation_time_ms=elapsed_ms,
        )

    def list_voices(self) -> list[VoiceInfo]:
        """Discover voices from the installed Chatterbox package + reference clips.

        Does not hardcode language/voice names — languages come from
        ``ChatterboxMultilingualTTS.get_supported_languages()`` when available.
        """
        self._ensure_runtime()
        voices: list[VoiceInfo] = []

        caps = _probe_capabilities()
        if caps.english or caps.multilingual or caps.turbo:
            voices.append(
                VoiceInfo(
                    voice_id=DEFAULT_VOICE_ID,
                    name="Chatterbox Default",
                    language="en",
                    description="Built-in Chatterbox voice (no reference clip)",
                    sample_text=_DEFAULT_SAMPLE_TEXT,
                )
            )

        if caps.multilingual and caps.supported_languages:
            for code, label in sorted(
                caps.supported_languages.items(),
                key=lambda item: str(item[1]).casefold(),
            ):
                code_s = str(code).strip().casefold()
                if not code_s:
                    continue
                if code_s == "en":
                    continue  # covered by Default
                voices.append(
                    VoiceInfo(
                        voice_id=f"lang:{code_s}",
                        name=str(label).strip() or code_s.upper(),
                        language=code_s,
                        description="Chatterbox multilingual language profile",
                        sample_text=_DEFAULT_SAMPLE_TEXT,
                    )
                )

        for path in self._discover_reference_clips():
            stem = path.stem
            voices.append(
                VoiceInfo(
                    voice_id=f"ref:{stem}",
                    name=display_name_from_id(stem) or stem,
                    language="",
                    description=f"Reference clip ({path.suffix.lstrip('.')})",
                    sample_text=_DEFAULT_SAMPLE_TEXT,
                )
            )

        if not voices:
            raise ProviderError(
                "No Chatterbox voices found. "
                f"{CHATTERBOX_UNAVAILABLE_MESSAGE} "
                f"Optional reference clips can be placed in {self._voices_dir}."
            )

        voices.sort(key=lambda item: (item.language.casefold(), item.name.casefold()))
        # Keep Default first when present.
        voices.sort(key=lambda item: 0 if item.voice_id == DEFAULT_VOICE_ID else 1)
        return voices

    def list_models(self) -> list[str]:
        caps = _probe_capabilities()
        models: list[str] = []
        if caps.english:
            models.append("chatterbox")
        if caps.multilingual:
            models.append("chatterbox-multilingual")
        if caps.turbo:
            models.append("chatterbox-turbo")
        return models or [CHATTERBOX_MODEL_ID]

    def test_connection(self) -> str:
        self.validate_ready()
        voices = self.list_voices()
        caps = _probe_capabilities()
        engines = []
        if caps.english:
            engines.append("english")
        if caps.multilingual:
            engines.append("multilingual")
        if caps.turbo:
            engines.append("turbo")
        return (
            f"Chatterbox ready ({len(voices)} voice(s); "
            f"engines: {', '.join(engines) or 'unknown'}; "
            f"reference clips in {self._voices_dir})."
        )

    def validate_ready(self) -> None:
        self._ensure_runtime()
        caps = _probe_capabilities()
        if not (caps.english or caps.multilingual or caps.turbo):
            raise ProviderError(
                "Chatterbox package is installed but no TTS engine class was found "
                "(expected ChatterboxTTS, ChatterboxMultilingualTTS, or "
                f"ChatterboxTurboTTS). {CHATTERBOX_UNAVAILABLE_MESSAGE}"
            )

    def _ensure_runtime(self) -> None:
        try:
            import chatterbox  # noqa: F401
        except ImportError as exc:
            raise ProviderError(f"{CHATTERBOX_UNAVAILABLE_MESSAGE} ({exc})") from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"{CHATTERBOX_UNAVAILABLE_MESSAGE} ({exc})") from exc

        caps = _probe_capabilities()
        if not (caps.english or caps.multilingual or caps.turbo):
            raise ProviderError(
                "Chatterbox is importable but no TTS engines were found. "
                f"{CHATTERBOX_UNAVAILABLE_MESSAGE}"
            )

    def _discover_reference_clips(self) -> list[Path]:
        if not self._voices_dir.is_dir():
            return []
        found: list[Path] = []
        for path in sorted(self._voices_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.casefold() not in _REF_SUFFIXES:
                continue
            found.append(path.resolve())
        return found

    def _synthesize_wav(
        self,
        text: str,
        *,
        voice_id: str,
        language_id: str,
        reference_path: str,
    ) -> tuple[bytes, str]:
        engine, kind = self._get_engine(language_id=language_id, reference_path=reference_path)
        kwargs: dict[str, Any] = {}
        if reference_path:
            kwargs["audio_prompt_path"] = reference_path
        if kind == "multilingual":
            if not language_id:
                raise ProviderError(
                    "Chatterbox multilingual synthesis requires a language id. "
                    "Set the channel language or pick a language voice."
                )
            kwargs["language_id"] = language_id
        elif kind == "turbo" and not reference_path:
            raise ProviderError(
                "Chatterbox Turbo requires a reference voice clip. "
                "Set Reference Voice in Channel Settings, or place a wav/mp3 under "
                f"{self._voices_dir}."
            )

        try:
            wav = engine.generate(text, **kwargs)
        except TypeError:
            # Older/narrower signatures — retry with fewer kwargs.
            if kind == "multilingual":
                wav = engine.generate(text, language_id, audio_prompt_path=reference_path or None)
            elif reference_path:
                wav = engine.generate(text, audio_prompt_path=reference_path)
            else:
                wav = engine.generate(text)

        sample_rate = int(getattr(engine, "sr", 24000) or 24000)
        return _tensor_to_wav_bytes(wav, sample_rate=sample_rate), f"{kind}.generate"

    def _get_engine(self, *, language_id: str, reference_path: str) -> tuple[Any, str]:
        kind = _select_engine_kind(language_id=language_id, reference_path=reference_path)
        if self._engine is not None and self._engine_kind == kind:
            return self._engine, kind

        device = _resolve_device()
        try:
            from app.core.ai_storage import apply_ai_storage_environment
            from app.providers.chatterbox_install import (
                ChatterboxModelMissingError,
                is_chatterbox_english_installed,
                require_chatterbox_english,
            )

            apply_ai_storage_environment()

            if kind == "multilingual":
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS

                try:
                    engine = ChatterboxMultilingualTTS.from_pretrained(
                        device=device, t3_model="v3"
                    )
                except TypeError:
                    engine = ChatterboxMultilingualTTS.from_pretrained(device=device)
            elif kind == "turbo":
                from chatterbox.tts_turbo import ChatterboxTurboTTS

                engine = ChatterboxTurboTTS.from_pretrained(device=device)
            else:
                from chatterbox.tts import ChatterboxTTS

                if not is_chatterbox_english_installed():
                    raise ChatterboxModelMissingError()
                local_dir = require_chatterbox_english()
                engine = ChatterboxTTS.from_local(local_dir, device)
        except ChatterboxModelMissingError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Failed to load Chatterbox '{kind}' model on device '{device}': {exc}"
            ) from exc

        self._engine = engine
        self._engine_kind = kind
        self._device = device
        return engine, kind


def resolve_chatterbox_voices_dir(data_root: Path | None = None) -> Path:
    """Canonical Chatterbox reference-clip folder: ``{data_root}/voices/chatterbox``."""
    if data_root is not None:
        from app.core.storage_paths import StoragePaths

        return (StoragePaths(data_root).voices / "chatterbox").resolve()
    return (Path.cwd() / "voices" / "chatterbox").resolve()


def ensure_chatterbox_voices_dir(data_root: Path | None = None) -> Path:
    path = resolve_chatterbox_voices_dir(data_root)
    path.mkdir(parents=True, exist_ok=True)
    return path


class _Capabilities:
    __slots__ = ("english", "multilingual", "turbo", "supported_languages")

    def __init__(self) -> None:
        self.english = False
        self.multilingual = False
        self.turbo = False
        self.supported_languages: dict[str, str] = {}


def _probe_capabilities() -> _Capabilities:
    caps = _Capabilities()
    try:
        from chatterbox.tts import ChatterboxTTS  # noqa: F401

        caps.english = True
    except Exception:  # noqa: BLE001
        caps.english = False
    try:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        caps.multilingual = True
        getter = getattr(ChatterboxMultilingualTTS, "get_supported_languages", None)
        if callable(getter):
            raw = getter()
            if isinstance(raw, dict):
                caps.supported_languages = {
                    str(k).strip().casefold(): str(v)
                    for k, v in raw.items()
                    if str(k).strip()
                }
        if not caps.supported_languages:
            # Fallback: module-level dict when classmethod missing.
            try:
                from chatterbox import mtl_tts as mtl_mod

                raw = getattr(mtl_mod, "SUPPORTED_LANGUAGES", {}) or {}
                if isinstance(raw, dict):
                    caps.supported_languages = {
                        str(k).strip().casefold(): str(v)
                        for k, v in raw.items()
                        if str(k).strip()
                    }
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        caps.multilingual = False
    try:
        from chatterbox.tts_turbo import ChatterboxTurboTTS  # noqa: F401

        caps.turbo = True
    except Exception:  # noqa: BLE001
        caps.turbo = False
    return caps


def _select_engine_kind(*, language_id: str, reference_path: str) -> str:
    caps = _probe_capabilities()
    lang = (language_id or "en").casefold()
    if lang and lang != "en" and caps.multilingual:
        return "multilingual"
    if caps.english:
        return "english"
    if caps.multilingual:
        return "multilingual"
    if caps.turbo:
        return "turbo"
    raise ProviderError(
        "No usable Chatterbox engine is available. "
        f"{CHATTERBOX_UNAVAILABLE_MESSAGE}"
    )


def _resolve_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            return "mps"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def _clean_id(raw: str) -> str:
    cleaned = (raw or "").strip()
    if not cleaned or cleaned in {"local_default"}:
        return ""
    # Kokoro default leaking into Chatterbox settings is not a Chatterbox voice.
    return cleaned


def _language_id_for(*, voice_id: str, language: str) -> str:
    if voice_id.startswith("lang:"):
        return voice_id.split(":", 1)[1].strip().casefold()
    raw = (language or "").strip()
    if not raw:
        return "en"
    # en-US / nl_NL → en / nl
    primary = raw.replace("_", "-").split("-", 1)[0].casefold()
    return primary or "en"


def _resolve_reference_path(
    *,
    request_path: str,
    settings_path: str,
    voice_id: str,
    voices_dir: Path,
) -> str:
    for candidate in (request_path, settings_path):
        cleaned = (candidate or "").strip()
        if not cleaned:
            continue
        path = Path(cleaned).expanduser()
        if path.is_file():
            return str(path.resolve())
        raise ProviderError(
            f"Chatterbox reference voice file was not found: {cleaned}"
        )
    if voice_id.startswith("ref:"):
        stem = voice_id.split(":", 1)[1].strip()
        for path in voices_dir.rglob("*"):
            if path.is_file() and path.stem == stem and path.suffix.casefold() in _REF_SUFFIXES:
                return str(path.resolve())
        raise ProviderError(
            f"Chatterbox reference voice '{stem}' was not found under {voices_dir}."
        )
    return ""


def _tensor_to_wav_bytes(wav: Any, *, sample_rate: int) -> bytes:
    """Convert a Chatterbox waveform (tensor / ndarray) to a WAV payload."""
    try:
        import numpy as np
    except ImportError as exc:
        raise ProviderError(
            f"numpy is required for Chatterbox WAV export ({exc})."
        ) from exc

    if hasattr(wav, "detach"):
        wav = wav.detach().cpu().numpy()
    array = np.asarray(wav)
    if array.ndim > 1:
        array = array.squeeze()
    if array.ndim != 1:
        array = array.reshape(-1)
    # Float → int16 PCM
    if array.dtype.kind == "f":
        array = np.clip(array, -1.0, 1.0)
        pcm = (array * 32767.0).astype(np.int16)
    else:
        pcm = array.astype(np.int16, copy=False)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(max(1, int(sample_rate)))
        wav_file.writeframes(pcm.tobytes())
    return buffer.getvalue()
