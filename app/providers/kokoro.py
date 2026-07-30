"""Kokoro voice provider — ONNX runtime behind the VoiceProvider ABC.

Uses ``kokoro-onnx`` (Python 3.10–3.13). The Voice Pipeline / Service /
Generator remain provider-agnostic. If the official hexgrad ``kokoro`` package
later supports Python 3.13, only this module needs to change.
"""

from __future__ import annotations

import io
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

from app.core.voice_settings import VoiceSettings
from app.providers.errors import ProviderError
from app.providers.health import HealthCheckItem, ProviderHealth
from app.providers.voice_base import (
    VoiceInfo,
    VoiceProvider,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)
from app.providers.voice_metadata import display_name_from_id

KOKORO_PROVIDER_ID = "kokoro"
KOKORO_PROVIDER_LABEL = "Kokoro (Recommended)"
KOKORO_SAMPLE_RATE = 24_000
KOKORO_MODEL_ID = "kokoro-82m-onnx"
_DEFAULT_VOICE_ID = "af_heart"

_MODEL_FILENAME = "kokoro-v1.0.onnx"
_VOICES_FILENAME = "voices-v1.0.bin"
_MODEL_RELEASE_BASE = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)

# Optional style labels for known voice ids — never used as the discovery source.
_STYLE_HINTS: dict[str, tuple[str, ...]] = {
    "af_heart": ("Warm", "Soft", "Intimate"),
    "af_bella": ("Warm", "Friendly", "Clear"),
    "af_nicole": ("Clear", "Neutral"),
    "af_sarah": ("Warm", "Calm"),
    "af_sky": ("Bright", "Youthful"),
    "af_nova": ("Modern", "Clear"),
    "am_adam": ("Clear", "Neutral", "Documentary"),
    "am_michael": ("Deep", "Calm", "Documentary", "Authoritative", "Cinematic"),
    "am_eric": ("Confident", "Modern", "Engaging"),
    "am_fenrir": ("Deep", "Authoritative"),
    "am_puck": ("Energetic", "Playful"),
    "bf_emma": ("Warm", "Clear"),
    "bf_isabella": ("Soft", "Warm"),
    "bm_george": ("Deep", "Calm", "Documentary", "Authoritative"),
    "bm_lewis": ("Clear", "Neutral"),
}

_DEFAULT_SAMPLE_TEXT = (
    "Hollow Atlas explores the greatest mysteries of human history."
)

KOKORO_UNAVAILABLE_MESSAGE = (
    "Kokoro (ONNX) is not installed or not ready. "
    "Install with: pip install -r requirements-voice-local.txt "
    "(kokoro-onnx supports Python 3.10–3.13). "
    "Optional cloud providers remain available in Settings."
)

_HEALTH_TEST_SENTENCE = "Hello."
_HEALTH_CHECK_KEYS = (
    "kokoro_onnx",
    "onnxruntime",
    "model_files",
    "synthesis",
)


class KokoroProvider(VoiceProvider):
    """Local Kokoro TTS via kokoro-onnx. Returns WAV bytes only."""

    def __init__(
        self,
        settings: VoiceSettings,
        *,
        model_dir: Path | None = None,
        auto_download_models: bool = True,
    ) -> None:
        self._settings = settings
        self._model_dir = (
            model_dir.expanduser().resolve()
            if model_dir is not None
            else Path.cwd() / "kokoro_models"
        )
        self._auto_download_models = auto_download_models
        self._engine: Any | None = None

    @property
    def provider_id(self) -> str:
        return KOKORO_PROVIDER_ID

    @property
    def settings(self) -> VoiceSettings:
        return self._settings

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        settings = self._settings
        text = (request.text or "").strip()
        if not text:
            raise ProviderError("Script text is empty — nothing to synthesize.")

        voice_id = _resolve_voice_id(request.voice_id or settings.voice_id)
        speed = request.speed if request.speed > 0 else float(settings.speed or 1.0)
        speed = min(2.0, max(0.5, speed))
        language = (request.language or settings.language or "").strip()
        lang = _onnx_lang(voice_id=voice_id, language=language)

        self.validate_ready()
        engine = self._get_engine()

        started = time.perf_counter()
        try:
            samples, sample_rate = engine.create(
                text,
                voice=voice_id,
                speed=float(speed),
                lang=lang,
            )
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Kokoro synthesis failed: {exc}") from exc

        try:
            wav_bytes = _float_audio_to_wav_bytes(samples, sample_rate=int(sample_rate))
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Kokoro audio encoding failed: {exc}") from exc

        if not wav_bytes:
            raise ProviderError("Kokoro produced an empty WAV payload.")

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return VoiceSynthesisResponse(
            audio_bytes=wav_bytes,
            content_type="audio/wav",
            model=KOKORO_MODEL_ID,
            voice_id=voice_id,
            generation_time_ms=elapsed_ms,
        )

    def list_voices(self) -> list[VoiceInfo]:
        """Enumerate voices from the ONNX runtime. Never hardcodes the catalogue."""
        try:
            self._ensure_runtime()
            self._ensure_model_files()
            engine = self._get_engine()
            names = list(engine.get_voices())
        except ProviderError:
            return []
        except Exception:  # noqa: BLE001
            return []

        voices: list[VoiceInfo] = []
        for voice_id in names:
            cleaned = str(voice_id or "").strip()
            if cleaned:
                voices.append(_voice_info_from_id(cleaned))
        voices.sort(key=lambda item: (item.gender.casefold(), item.name.casefold()))
        return voices

    def list_models(self) -> list[str]:
        return [KOKORO_MODEL_ID]

    def test_connection(self) -> str:
        self.validate_ready()
        voices = self.list_voices()
        return (
            f"Kokoro ONNX ready ({len(voices)} voice(s); "
            f"models in {self._model_dir})."
        )

    def validate_ready(self) -> None:
        self._ensure_runtime()
        self._ensure_model_files()
        self._get_engine()

    def health_check(self) -> ProviderHealth:
        """Lightweight self-test for diagnostics / Settings UI.

        Does not raise — returns a structured ``ProviderHealth`` describing:
        kokoro-onnx install, ONNX Runtime, model files, and a tiny synthesis.
        Does not touch the Voice Pipeline.
        """
        started = time.perf_counter()
        checks: list[HealthCheckItem] = []

        package_ok = self._health_check_package(checks)
        runtime_ok = self._health_check_onnxruntime(checks)
        models_ok = False
        synthesis_ok = False

        if package_ok and runtime_ok:
            models_ok = self._health_check_model_files(checks)
        else:
            checks.append(
                HealthCheckItem(
                    "model_files",
                    False,
                    "Skipped — package or ONNX Runtime not available.",
                )
            )

        if models_ok:
            synthesis_ok = self._health_check_synthesis(checks)
        else:
            checks.append(
                HealthCheckItem(
                    "synthesis",
                    False,
                    "Skipped — model files not ready.",
                )
            )

        ok = package_ok and runtime_ok and models_ok and synthesis_ok
        if ok:
            message = (
                f"Kokoro ONNX healthy "
                f"(models in {self._model_dir}; synthesized test audio)."
            )
        else:
            failed = [item.key for item in checks if not item.ok]
            message = "Kokoro ONNX health check failed: " + ", ".join(failed) + "."

        return ProviderHealth(
            ok=ok,
            provider_id=KOKORO_PROVIDER_ID,
            message=message,
            checks=tuple(checks),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    def _health_check_package(self, checks: list[HealthCheckItem]) -> bool:
        try:
            from kokoro_onnx import Kokoro  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            checks.append(
                HealthCheckItem(
                    "kokoro_onnx",
                    False,
                    f"Not installed or failed to import: {exc}",
                )
            )
            return False
        checks.append(HealthCheckItem("kokoro_onnx", True, "Package available."))
        return True

    def _health_check_onnxruntime(self, checks: list[HealthCheckItem]) -> bool:
        try:
            import onnxruntime as ort
        except Exception as exc:  # noqa: BLE001
            checks.append(
                HealthCheckItem(
                    "onnxruntime",
                    False,
                    f"Not available: {exc}",
                )
            )
            return False
        version = getattr(ort, "__version__", "")
        detail = f"Available ({version})." if version else "Available."
        checks.append(HealthCheckItem("onnxruntime", True, detail))
        return True

    def _health_check_model_files(self, checks: list[HealthCheckItem]) -> bool:
        try:
            self._ensure_model_files()
        except Exception as exc:  # noqa: BLE001
            checks.append(
                HealthCheckItem(
                    "model_files",
                    False,
                    str(exc),
                )
            )
            return False
        model_path = self._model_dir / _MODEL_FILENAME
        voices_path = self._model_dir / _VOICES_FILENAME
        if not model_path.is_file() or not voices_path.is_file():
            checks.append(
                HealthCheckItem(
                    "model_files",
                    False,
                    f"Expected {_MODEL_FILENAME} and {_VOICES_FILENAME} in {self._model_dir}.",
                )
            )
            return False
        checks.append(
            HealthCheckItem(
                "model_files",
                True,
                f"Present in {self._model_dir}.",
            )
        )
        return True

    def _health_check_synthesis(self, checks: list[HealthCheckItem]) -> bool:
        try:
            response = self.synthesize(
                VoiceSynthesisRequest(
                    text=_HEALTH_TEST_SENTENCE,
                    voice_id=_resolve_voice_id(self._settings.voice_id),
                    language=(self._settings.language or "en-US").strip(),
                    output_format="wav",
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                HealthCheckItem(
                    "synthesis",
                    False,
                    f"Test synthesis failed: {exc}",
                )
            )
            return False
        if not response.audio_bytes or not response.audio_bytes.startswith(b"RIFF"):
            checks.append(
                HealthCheckItem(
                    "synthesis",
                    False,
                    "Test synthesis returned empty or non-WAV audio.",
                )
            )
            return False
        checks.append(
            HealthCheckItem(
                "synthesis",
                True,
                f"Synthesized {_HEALTH_TEST_SENTENCE!r} "
                f"({len(response.audio_bytes)} bytes WAV).",
            )
        )
        return True

    def _ensure_runtime(self) -> None:
        missing: list[str] = []
        for module_name in ("kokoro_onnx", "numpy", "onnxruntime"):
            try:
                __import__(module_name)
            except ImportError:
                missing.append(module_name)
        if missing:
            raise ProviderError(
                f"{KOKORO_UNAVAILABLE_MESSAGE} Missing modules: {', '.join(missing)}."
            )
        try:
            from kokoro_onnx import Kokoro  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"{KOKORO_UNAVAILABLE_MESSAGE} ({exc})") from exc

    def _ensure_model_files(self) -> None:
        self._model_dir.mkdir(parents=True, exist_ok=True)
        model_path = self._model_dir / _MODEL_FILENAME
        voices_path = self._model_dir / _VOICES_FILENAME
        missing = [
            path.name for path in (model_path, voices_path) if not path.is_file()
        ]
        if not missing:
            return
        if not self._auto_download_models:
            raise ProviderError(
                "Kokoro model files are missing: "
                + ", ".join(missing)
                + f". Place them in {self._model_dir} "
                f"(from {_MODEL_RELEASE_BASE}/)."
            )
        try:
            if not model_path.is_file():
                _download_file(f"{_MODEL_RELEASE_BASE}/{_MODEL_FILENAME}", model_path)
            if not voices_path.is_file():
                _download_file(f"{_MODEL_RELEASE_BASE}/{_VOICES_FILENAME}", voices_path)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Failed to download Kokoro model files into {self._model_dir}: {exc}. "
                f"Download manually from {_MODEL_RELEASE_BASE}/"
            ) from exc

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        from kokoro_onnx import Kokoro

        model_path = self._model_dir / _MODEL_FILENAME
        voices_path = self._model_dir / _VOICES_FILENAME
        try:
            self._engine = Kokoro(str(model_path), str(voices_path))
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Failed to initialize Kokoro ONNX: {exc}") from exc
        return self._engine


def _voice_info_from_id(voice_id: str) -> VoiceInfo:
    """Build catalogue metadata from a discovered Kokoro voice id."""
    prefix = voice_id[:2].casefold() if len(voice_id) >= 2 else ""
    if prefix == "af":
        gender, language, accent = "Female", "en-US", "American"
    elif prefix == "am":
        gender, language, accent = "Male", "en-US", "American"
    elif prefix == "bf":
        gender, language, accent = "Female", "en-GB", "British"
    elif prefix == "bm":
        gender, language, accent = "Male", "en-GB", "British"
    else:
        gender, language, accent = "", _language_label_for_voice(voice_id), ""

    name = display_name_from_id(voice_id)
    styles = _STYLE_HINTS.get(voice_id.casefold()) or _STYLE_HINTS.get(voice_id) or ()
    if not styles:
        # Lightweight heuristics from the display name — still not a fixed catalogue.
        lowered = name.casefold()
        guessed: list[str] = []
        if any(token in lowered for token in ("nova", "sky", "puck")):
            guessed.extend(["Energetic", "Modern", "Engaging"])
        if any(token in lowered for token in ("michael", "george", "fenrir")):
            guessed.extend(["Deep", "Calm", "Documentary", "Authoritative"])
        if gender == "Female":
            guessed.extend(["Warm", "Clear"])
        elif gender == "Male":
            guessed.extend(["Clear", "Confident"])
        styles = tuple(dict.fromkeys(guessed))

    return VoiceInfo(
        voice_id=voice_id,
        name=name,
        language=language,
        description="",
        gender=gender,
        accent=accent,
        age="",
        style_tags=tuple(styles),
        sample_text=_DEFAULT_SAMPLE_TEXT,
    )


def _resolve_voice_id(raw: str) -> str:
    voice_id = str(raw or "").strip()
    if not voice_id or voice_id in {"local_default", "default"}:
        return _DEFAULT_VOICE_ID
    return voice_id


def _onnx_lang(*, voice_id: str, language: str) -> str:
    """Map settings / voice id to kokoro-onnx lang (e.g. en-us, en-gb)."""
    lang = language.casefold().replace("_", "-")
    if lang.startswith("en-gb") or lang in {"en-uk", "gb"}:
        return "en-gb"
    if lang.startswith("en-us") or lang in {"en", "us", "a", ""}:
        prefix = voice_id[:1].casefold()
        if prefix == "b":
            return "en-gb"
        return "en-us"
    if lang:
        return lang
    return "en-gb" if voice_id[:1].casefold() == "b" else "en-us"


def _language_label_for_voice(voice_id: str) -> str:
    return "en-GB" if voice_id[:1].casefold() == "b" else "en-US"


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    try:
        with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310
            data = response.read()
        if not data:
            raise ProviderError(f"Empty download from {url}")
        partial.write_bytes(data)
        partial.replace(destination)
    except urllib.error.URLError as exc:
        raise ProviderError(str(exc)) from exc
    finally:
        if partial.exists() and not destination.exists():
            partial.unlink(missing_ok=True)


def _float_audio_to_wav_bytes(audio: Any, *, sample_rate: int) -> bytes:
    import numpy as np

    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    clipped = np.clip(np.asarray(audio, dtype=np.float32).reshape(-1), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(sample_rate))
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


# Backward-compatible alias used by older unit tests / docs.
def _lang_code_for(*, voice_id: str, language: str) -> str:
    """Deprecated alias — returns ONNX lang string (en-us / en-gb)."""
    return _onnx_lang(voice_id=voice_id, language=language)
