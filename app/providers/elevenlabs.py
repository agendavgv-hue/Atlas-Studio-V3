"""ElevenLabs voice provider."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.core.voice_settings import VoiceSettings
from app.providers.errors import ProviderError
from app.providers.voice_base import (
    VoiceInfo,
    VoiceProvider,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)

_API_BASE = "https://api.elevenlabs.io/v1"
# Sensible catalogue when the account endpoint does not list models.
_DEFAULT_MODELS = (
    "eleven_multilingual_v2",
    "eleven_turbo_v2_5",
    "eleven_flash_v2_5",
    "eleven_monolingual_v1",
)


class ElevenLabsVoiceProvider(VoiceProvider):
    def __init__(self, settings: VoiceSettings) -> None:
        self._settings = settings

    @property
    def provider_id(self) -> str:
        return "elevenlabs"

    @property
    def settings(self) -> VoiceSettings:
        return self._settings

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResponse:
        settings = self._settings
        text = (request.text or "").strip()
        if not text:
            raise ProviderError("Script text is empty — nothing to synthesize.")

        voice_id = (request.voice_id or settings.voice_id).strip()
        if not voice_id:
            raise ProviderError("No voice selected. Configure Voice in Settings.")

        model = (request.model or settings.model).strip()
        output_format = (request.output_format or settings.output_format).strip()
        stability = request.stability if request.stability > 0 else settings.stability
        style = request.style if request.style > 0 else settings.style
        speed = request.speed if request.speed > 0 else settings.speed
        similarity = request.similarity if request.similarity > 0 else settings.similarity
        language = (request.language or settings.language).strip()

        payload: dict[str, Any] = {
            "text": text,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity,
                "style": style,
                "use_speaker_boost": True,
                "speed": speed,
            },
        }
        if model:
            payload["model_id"] = model
        if language:
            payload["language_code"] = language

        query = urllib.parse.urlencode({"output_format": output_format}) if output_format else ""
        path = f"/text-to-speech/{urllib.parse.quote(voice_id)}"
        if query:
            path = f"{path}?{query}"

        started = time.perf_counter()
        audio = self._post_audio(path, payload)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        if not audio:
            raise ProviderError("ElevenLabs returned empty audio.")

        return VoiceSynthesisResponse(
            audio_bytes=audio,
            content_type="audio/mpeg",
            model=model,
            voice_id=voice_id,
            generation_time_ms=elapsed_ms,
        )

    def list_voices(self) -> list[VoiceInfo]:
        body = self._get_json("/voices")
        voices_raw = body.get("voices") if isinstance(body, dict) else None
        if not isinstance(voices_raw, list):
            raise ProviderError("Unexpected ElevenLabs voices response.")
        voices: list[VoiceInfo] = []
        for entry in voices_raw:
            if not isinstance(entry, dict):
                continue
            voice_id = str(entry.get("voice_id") or "").strip()
            name = str(entry.get("name") or "").strip() or voice_id
            if not voice_id:
                continue
            labels = entry.get("labels") if isinstance(entry.get("labels"), dict) else {}
            language = str(labels.get("language") or labels.get("accent") or "").strip()
            description = str(entry.get("description") or "").strip()
            voices.append(
                VoiceInfo(
                    voice_id=voice_id,
                    name=name,
                    language=language,
                    description=description,
                )
            )
        voices.sort(key=lambda item: item.name.casefold())
        return voices

    def list_models(self) -> list[str]:
        try:
            body = self._get_json("/models")
        except ProviderError:
            return list(_DEFAULT_MODELS)
        if not isinstance(body, list):
            return list(_DEFAULT_MODELS)
        names: list[str] = []
        for entry in body:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("model_id") or entry.get("modelId") or "").strip()
            if model_id:
                names.append(model_id)
        return names or list(_DEFAULT_MODELS)

    def test_connection(self) -> str:
        if not self._settings.api_key.strip():
            raise ProviderError("ElevenLabs API key is empty.")
        voices = self.list_voices()
        if not voices:
            raise ProviderError("ElevenLabs connected but returned no voices.")
        return f"ElevenLabs OK — {len(voices)} voice(s) available."

    def validate_ready(self) -> None:
        if not self._settings.api_key.strip():
            raise ProviderError("ElevenLabs API key is empty. Open Settings → Voice Provider.")
        if not self._settings.voice_id.strip():
            raise ProviderError(
                "No voice selected. Open Settings, Test Connection, and choose a voice."
            )
        message = self.test_connection()
        voices = self.list_voices()
        ids = {item.voice_id for item in voices}
        if self._settings.voice_id not in ids:
            raise ProviderError(
                f"Selected voice '{self._settings.voice_id}' was not found on this account. "
                f"{message}"
            )

    def _headers(self, *, accept: str = "application/json") -> dict[str, str]:
        key = self._settings.api_key.strip()
        if not key:
            raise ProviderError("ElevenLabs API key is empty.")
        return {
            "xi-api-key": key,
            "Accept": accept,
            "Content-Type": "application/json",
        }

    def _get_json(self, path: str) -> Any:
        url = f"{_API_BASE}{path}"
        request = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ProviderError(self._http_error_message(exc)) from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"ElevenLabs unreachable: {exc.reason}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError("ElevenLabs returned invalid JSON.") from exc

    def _post_audio(self, path: str, payload: dict[str, Any]) -> bytes:
        url = f"{_API_BASE}{path}"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(accept="audio/mpeg"),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise ProviderError(self._http_error_message(exc)) from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"ElevenLabs unreachable: {exc.reason}") from exc

    @staticmethod
    def _http_error_message(exc: urllib.error.HTTPError) -> str:
        detail = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                detail = str(
                    parsed.get("detail")
                    or parsed.get("message")
                    or parsed.get("error")
                    or body
                )[:240]
            else:
                detail = body[:240]
        except Exception:  # noqa: BLE001
            detail = ""
        if exc.code in {401, 403}:
            base = "ElevenLabs API key is invalid or unauthorized."
        elif exc.code == 404:
            base = "ElevenLabs voice or endpoint not found."
        else:
            base = f"ElevenLabs HTTP {exc.code}."
        return f"{base} {detail}".strip()
