"""Piper voice provider — local ONNX TTS behind the VoiceProvider ABC.

Discovers voices by scanning ``voices/piper/*.onnx`` (no hardcoded catalogue).
Uses the ``piper-tts`` package when installed. The Voice Pipeline / Service /
Generator remain provider-agnostic.
"""

from __future__ import annotations

import io
import json
import logging
import re
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

PIPER_PROVIDER_ID = "piper"
PIPER_PROVIDER_LABEL = "Piper (Local)"
PIPER_MODEL_ID = "piper-onnx"

PIPER_UNAVAILABLE_MESSAGE = (
    "Piper is not installed or not ready. "
    "Install with: pip install piper-tts "
    "(or pip install -r requirements-voice-local.txt). "
    "Place voice models as *.onnx files under voices/piper/."
)

_DEFAULT_SAMPLE_TEXT = (
    "Atlas Studio generates premium documentary narration offline."
)

# Piper model stems often look like: en_US-lessac-medium
_LANG_PREFIX = re.compile(r"^([a-z]{2})[_-]([A-Z]{2})\b")


class PiperVoiceProvider(VoiceProvider):
    """Local Piper TTS. Returns WAV bytes only. Catalogue = folder scan."""

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
            else (Path.cwd() / "voices" / "piper").resolve()
        )
        # Always materialize the scan folder so users know where models belong.
        self._voices_dir.mkdir(parents=True, exist_ok=True)
        self._loaded: dict[str, Any] = {}

    @property
    def provider_id(self) -> str:
        return PIPER_PROVIDER_ID

    @property
    def settings(self) -> VoiceSettings:
        return self._settings

    @property
    def model_dir(self) -> Path:
        """Piper models folder (same role as Kokoro's model_dir for discovery UI)."""
        return self._voices_dir

    @property
    def voices_dir(self) -> Path:
        return self._voices_dir

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        text = (request.text or "").strip()
        if not text:
            raise ProviderError("Script text is empty — nothing to synthesize.")

        # Prefer the request voice; settings may still hold a Kokoro id after
        # switching providers — never synthesize without a real Piper *.onnx.
        request_voice = _resolve_voice_id(request.voice_id)
        settings_voice = _resolve_voice_id(self._settings.voice_id)
        voice_id = request_voice or settings_voice
        if not voice_id:
            raise ProviderError("No Piper voice selected.")

        onnx_path = self._onnx_path_for(voice_id)
        if onnx_path is None:
            if not request_voice:
                # Leftover non-Piper settings voice (e.g. Kokoro af_heart).
                raise ProviderError("No Piper voice selected.")
            raise ProviderError(
                f"Piper voice '{voice_id}' was not found under {self._voices_dir}. "
                "Add a matching *.onnx model file."
            )

        language = (request.language or self._settings.language or "").strip()
        model = (request.model or self._settings.model or PIPER_MODEL_ID).strip()
        speed = request.speed if request.speed > 0 else float(self._settings.speed or 1.0)
        speed = min(2.0, max(0.5, speed))
        length_scale = 1.0 / speed if speed > 0 else 1.0

        logger.info(
            "Piper synthesis request | provider=%s | voice=%s | model=%s | "
            "language=%s | model_path=%s | length_scale=%.3f | output=wav-bytes",
            self.provider_id,
            voice_id,
            model,
            language or "(unset)",
            onnx_path,
            length_scale,
        )

        self.validate_ready()
        engine = self._load_voice(onnx_path)

        started = time.perf_counter()
        try:
            wav_bytes, command = _synthesize_wav_bytes(
                engine,
                text,
                length_scale=length_scale,
            )
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Piper synthesis failed: {exc}") from exc

        if not wav_bytes:
            raise ProviderError("Piper produced an empty WAV payload.")

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "Piper synthesis ok | command=%s | model_path=%s | "
            "output_path=in-memory-wav | bytes=%s | ms=%s",
            command,
            onnx_path,
            len(wav_bytes),
            elapsed_ms,
        )
        return VoiceSynthesisResponse(
            audio_bytes=wav_bytes,
            content_type="audio/wav",
            model=model or PIPER_MODEL_ID,
            voice_id=voice_id,
            generation_time_ms=elapsed_ms,
        )

    def list_voices(self) -> list[VoiceInfo]:
        """Enumerate every ``*.onnx`` model under ``voices/piper/``."""
        self._ensure_runtime()
        paths = self._discover_onnx_paths()
        if not paths:
            raise ProviderError(
                "No Piper voices found. "
                f"Place *.onnx model files in {self._voices_dir}."
            )

        voices: list[VoiceInfo] = []
        for path in paths:
            voices.append(_voice_info_from_path(path))
        voices.sort(key=lambda item: (item.language.casefold(), item.name.casefold()))
        return voices

    def list_models(self) -> list[str]:
        return [PIPER_MODEL_ID]

    def test_connection(self) -> str:
        self.validate_ready()
        voices = self.list_voices()
        return (
            f"Piper ready ({len(voices)} voice(s); "
            f"models in {self._voices_dir})."
        )

    def validate_ready(self) -> None:
        self._ensure_runtime()
        if not self._voices_dir.is_dir():
            raise ProviderError(
                f"Piper voices folder is missing: {self._voices_dir}. "
                "Create it and add *.onnx voice models."
            )
        if not self._discover_onnx_paths():
            raise ProviderError(
                f"No Piper *.onnx models found in {self._voices_dir}."
            )

    def _ensure_runtime(self) -> None:
        try:
            from piper.voice import PiperVoice  # noqa: F401
        except ImportError as exc:
            raise ProviderError(f"{PIPER_UNAVAILABLE_MESSAGE} ({exc})") from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"{PIPER_UNAVAILABLE_MESSAGE} ({exc})") from exc

    def _discover_onnx_paths(self) -> list[Path]:
        if not self._voices_dir.is_dir():
            return []
        found: list[Path] = []
        for path in sorted(self._voices_dir.rglob("*.onnx")):
            if not path.is_file():
                continue
            # Skip accidental config-named onnx; Piper uses .onnx + .onnx.json.
            if path.name.endswith(".json"):
                continue
            found.append(path.resolve())
        return found

    def _onnx_path_for(self, voice_id: str) -> Path | None:
        wanted = (voice_id or "").strip()
        if not wanted:
            return None
        for path in self._discover_onnx_paths():
            if path.stem == wanted or path.name == wanted:
                return path
            # Allow relative ids from nested folders: lang/voice.onnx
            try:
                rel = path.relative_to(self._voices_dir).as_posix()
            except ValueError:
                rel = path.name
            if rel == wanted or rel.removesuffix(".onnx") == wanted:
                return path
        # Absolute / existing path passed as voice_id
        candidate = Path(wanted)
        if candidate.is_file() and candidate.suffix.casefold() == ".onnx":
            return candidate.resolve()
        return None

    def _load_voice(self, onnx_path: Path) -> Any:
        key = str(onnx_path)
        cached = self._loaded.get(key)
        if cached is not None:
            return cached
        from piper.voice import PiperVoice

        config_path = _config_path_for(onnx_path)
        try:
            if config_path is not None:
                engine = PiperVoice.load(str(onnx_path), config_path=str(config_path))
            else:
                engine = PiperVoice.load(str(onnx_path))
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Failed to load Piper model {onnx_path.name}: {exc}"
            ) from exc
        self._loaded[key] = engine
        return engine


def resolve_piper_voices_dir(data_root: Path | None = None) -> Path:
    """Canonical Piper models folder: ``{data_root}/voices/piper``.

    Falls back to ``./voices/piper`` when no data root is provided.
    Does not create the folder — use ``ensure_piper_voices_dir``.
    """
    if data_root is not None:
        from app.core.storage_paths import StoragePaths

        return (StoragePaths(data_root).voices / "piper").resolve()
    return (Path.cwd() / "voices" / "piper").resolve()


def ensure_piper_voices_dir(data_root: Path | None = None) -> Path:
    """Return the absolute Piper models folder, creating it if missing."""
    path = resolve_piper_voices_dir(data_root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path_for(onnx_path: Path) -> Path | None:
    """Piper ships optional ``model.onnx.json`` next to the ONNX file."""
    candidates = (
        Path(str(onnx_path) + ".json"),
        onnx_path.with_suffix(".onnx.json"),
        onnx_path.with_suffix(".json"),
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def _voice_info_from_path(path: Path) -> VoiceInfo:
    stem = path.stem
    language, gender, accent = _meta_from_stem(stem, path)
    name = _display_name_from_piper_stem(stem)
    description = ""
    config_path = _config_path_for(path)
    if config_path is not None:
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        if isinstance(raw, dict):
            language = str(raw.get("language") or language)
            dataset = raw.get("dataset") or raw.get("audio", {})
            if isinstance(dataset, dict):
                quality = str(dataset.get("quality") or "").strip()
                if quality:
                    description = quality
            elif isinstance(dataset, str) and dataset.strip():
                name = dataset.strip().replace("_", " ").title()
            num_speakers = raw.get("num_speakers")
            if isinstance(num_speakers, int) and num_speakers > 1:
                description = (
                    f"{description}; {num_speakers} speakers".strip("; ").strip()
                )

    return VoiceInfo(
        voice_id=stem,
        name=name or stem,
        language=language,
        description=description,
        gender=gender,
        accent=accent,
        sample_text=_DEFAULT_SAMPLE_TEXT,
    )


def _display_name_from_piper_stem(stem: str) -> str:
    """Human label from stems like ``en_US-lessac-medium`` → ``Lessac Medium``."""
    rest = re.sub(r"^[a-z]{2}[_-][A-Za-z]{2}[-_]", "", stem)
    if not rest:
        rest = stem
    cleaned = rest.replace("-", " ").replace("_", " ").strip()
    return cleaned.title() if cleaned else display_name_from_id(stem)


def _meta_from_stem(stem: str, path: Path) -> tuple[str, str, str]:
    """Best-effort language / gender / accent from Piper naming conventions."""
    match = _LANG_PREFIX.match(stem)
    language = ""
    accent = ""
    if match:
        language = f"{match.group(1)}-{match.group(2)}"
    # Nested folder hints: voices/piper/nl/… or en_US/…
    parent = path.parent.name
    if not language and re.match(r"^[a-z]{2}([-_][A-Z]{2})?$", parent):
        language = parent.replace("_", "-")
    gender = ""
    lowered = stem.casefold()
    if any(token in lowered for token in ("female", "woman", "girl")):
        gender = "Female"
    elif any(token in lowered for token in ("male", "man", "boy")):
        gender = "Male"
    if language.startswith("en-US"):
        accent = "American"
    elif language.startswith("en-GB"):
        accent = "British"
    return language, gender, accent


def _resolve_voice_id(raw: str) -> str:
    """Return an explicit Piper voice/model id — never invent a fallback."""
    cleaned = (raw or "").strip()
    if not cleaned or cleaned in {"default", "local_default"}:
        return ""
    if cleaned.casefold().endswith(".onnx"):
        return Path(cleaned).stem
    return cleaned


def _synthesis_config(length_scale: float) -> Any | None:
    """Build piper.config.SynthesisConfig when the installed package exposes it."""
    try:
        from piper.config import SynthesisConfig
    except ImportError:
        return None
    return SynthesisConfig(length_scale=float(length_scale))


def _synthesize_wav_bytes(
    engine: Any,
    text: str,
    *,
    length_scale: float,
) -> tuple[bytes, str]:
    """Return ``(wav_bytes, command_label)`` from a loaded PiperVoice.

    Supports current ``piper-tts`` (``synthesize_wav`` / chunk ``synthesize``)
    and older APIs (``synthesize_stream_raw`` / ``synthesize(text, wav_file)``).
    """
    syn_config = _synthesis_config(length_scale)

    # Current piper-tts: synthesize_wav(text, wav_file, syn_config=…)
    synthesize_wav = getattr(engine, "synthesize_wav", None)
    if callable(synthesize_wav):
        for label, call in (
            (
                "PiperVoice.synthesize_wav(syn_config)",
                (lambda w: synthesize_wav(text, w, syn_config=syn_config))
                if syn_config is not None
                else None,
            ),
            (
                "PiperVoice.synthesize_wav",
                lambda w: synthesize_wav(text, w),
            ),
        ):
            if call is None:
                continue
            buffer = io.BytesIO()
            try:
                with wave.open(buffer, "wb") as wav_file:
                    call(wav_file)
                data = buffer.getvalue()
                if data:
                    return data, label
            except TypeError:
                continue
            except Exception:  # noqa: BLE001
                # Fall through to other APIs / let outer handler wrap unexpected errors.
                if label.endswith("(syn_config)"):
                    continue
                raise


    # Current piper-tts: synthesize(text, syn_config=…) → AudioChunk iterable
    synthesize = getattr(engine, "synthesize", None)
    if callable(synthesize):
        chunk_wav = _wav_from_audio_chunks(engine, text, syn_config=syn_config)
        if chunk_wav:
            return chunk_wav, "PiperVoice.synthesize→AudioChunk"

    # Legacy: synthesize_stream_raw → PCM
    stream_raw = getattr(engine, "synthesize_stream_raw", None)
    if callable(stream_raw):
        try:
            chunks: list[bytes] = []
            try:
                for chunk in stream_raw(text, length_scale=length_scale):
                    chunks.append(bytes(chunk))
            except TypeError:
                for chunk in stream_raw(text):
                    chunks.append(bytes(chunk))
            pcm = b"".join(chunks)
            if pcm:
                sample_rate = int(
                    getattr(getattr(engine, "config", None), "sample_rate", 22050)
                )
                return (
                    _pcm16_to_wav_bytes(pcm, sample_rate=sample_rate),
                    "PiperVoice.synthesize_stream_raw",
                )
        except Exception:  # noqa: BLE001
            pass

    # Legacy: synthesize(text, wav_file, length_scale=…)
    if callable(synthesize):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            try:
                synthesize(text, wav_file, length_scale=length_scale)
            except TypeError:
                synthesize(text, wav_file)
        data = buffer.getvalue()
        if data:
            return data, "PiperVoice.synthesize(wav_file)"

    raise ProviderError(
        "PiperVoice has no usable synthesize / synthesize_wav API on this install."
    )


def _wav_from_audio_chunks(
    engine: Any,
    text: str,
    *,
    syn_config: Any | None,
) -> bytes:
    """Assemble WAV bytes from modern ``PiperVoice.synthesize`` AudioChunks."""
    synthesize = getattr(engine, "synthesize", None)
    if not callable(synthesize):
        return b""
    try:
        if syn_config is not None:
            try:
                iterable = synthesize(text, syn_config=syn_config)
            except TypeError:
                iterable = synthesize(text)
        else:
            iterable = synthesize(text)
    except TypeError:
        # Likely the legacy (text, wav_file) signature — let caller fall through.
        return b""

    pcm_parts: list[bytes] = []
    sample_rate = 22050
    sample_width = 2
    sample_channels = 1
    try:
        for chunk in iterable:
            rate = getattr(chunk, "sample_rate", None)
            if rate:
                sample_rate = int(rate)
            width = getattr(chunk, "sample_width", None)
            if width:
                sample_width = int(width)
            channels = getattr(chunk, "sample_channels", None)
            if channels:
                sample_channels = int(channels)
            raw = getattr(chunk, "audio_int16_bytes", None)
            if raw:
                pcm_parts.append(bytes(raw))
                continue
            array = getattr(chunk, "audio_int16_array", None)
            if array is not None:
                pcm_parts.append(bytes(array))
    except TypeError:
        return b""

    pcm = b"".join(pcm_parts)
    if not pcm:
        return b""
    return _pcm16_to_wav_bytes(
        pcm,
        sample_rate=sample_rate,
        sample_width=sample_width,
        sample_channels=sample_channels,
    )


def _pcm16_to_wav_bytes(
    pcm: bytes,
    *,
    sample_rate: int,
    sample_width: int = 2,
    sample_channels: int = 1,
) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(max(1, int(sample_channels)))
        wav_file.setsampwidth(max(1, int(sample_width)))
        wav_file.setframerate(max(1, int(sample_rate)))
        wav_file.writeframes(pcm)
    return buffer.getvalue()
