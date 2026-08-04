"""Single source of truth for TTS voice catalogue discovery.

Voice Settings UI, channel narrator pickers, and the Kokoro voice generator
must all go through this service — never construct providers ad-hoc with a
different model directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.channels.language import voice_matches_language
from app.core.app_config import AppConfig
from app.core.storage_paths import StoragePaths
from app.core.voice_settings import VoiceSettings
from app.providers.errors import ProviderConfigurationError, ProviderError
from app.providers.voice_base import VoiceInfo, VoiceProvider
from app.providers.voice_registry import (
    KOKORO_PROVIDER_ID,
    LOCAL_VOICE_PROVIDER_ID,
    PIPER_PROVIDER_ID,
    VoiceProviderRegistry,
)


@dataclass(frozen=True)
class VoiceDiscoveryResult:
    """Outcome of one catalogue discovery attempt."""

    voices: list[VoiceInfo] = field(default_factory=list)
    provider_id: str = ""
    model_dir: str = ""
    error: str = ""
    warning: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.voices) and not self.error

    @property
    def empty_message(self) -> str:
        """Human-readable reason when the Voice Library is empty."""
        if self.error:
            return self.error
        if self.warning:
            return self.warning
        if self.model_dir:
            return (
                f"No voices found for provider '{self.provider_id or 'unknown'}' "
                f"(model path: {self.model_dir})."
            )
        return (
            f"No voices found for provider '{self.provider_id or 'unknown'}'."
        )


class VoiceDiscoveryService:
    """Discover voices through the same registry path as voice generation."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._registry = VoiceProviderRegistry(config)

    @property
    def registry(self) -> VoiceProviderRegistry:
        return self._registry

    def kokoro_model_dir(self):
        """Canonical Kokoro model directory used by generation."""
        return StoragePaths(self._config.data_root).cache / "kokoro"

    def piper_voices_dir(self):
        """Canonical Piper models folder: ``{data_root}/voices/piper`` (created)."""
        from app.providers.piper import ensure_piper_voices_dir

        return ensure_piper_voices_dir(self._config.data_root)

    def resolve_provider(
        self,
        *,
        provider_id: str | None = None,
        settings: VoiceSettings | None = None,
    ) -> VoiceProvider:
        """Build the provider generation uses (same paths for Settings + VoiceService)."""
        return self._registry.require_voice_provider(
            provider_id=provider_id,
            settings=settings,
        )

    def discover(
        self,
        *,
        provider_id: str | None = None,
        settings: VoiceSettings | None = None,
        channel_language: str | None = None,
    ) -> VoiceDiscoveryResult:
        """List every voice the selected provider currently exposes.

        ``channel_language`` is an optional UI filter only. Discovery itself
        always returns the full provider catalogue first; filtering never
        hides the underlying error when the catalogue is empty.
        """
        resolved_id = (
            provider_id or self._config.voice_provider or KOKORO_PROVIDER_ID
        ).strip().casefold() or KOKORO_PROVIDER_ID
        if resolved_id == LOCAL_VOICE_PROVIDER_ID:
            resolved_id = KOKORO_PROVIDER_ID

        model_dir = ""
        if resolved_id == KOKORO_PROVIDER_ID:
            model_dir = str(self.kokoro_model_dir())
        elif resolved_id == PIPER_PROVIDER_ID:
            model_dir = str(self.piper_voices_dir())

        try:
            provider = self.resolve_provider(
                provider_id=resolved_id,
                settings=settings,
            )
        except ProviderConfigurationError as exc:
            return VoiceDiscoveryResult(
                provider_id=resolved_id,
                model_dir=model_dir,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return VoiceDiscoveryResult(
                provider_id=resolved_id,
                model_dir=model_dir,
                error=f"Could not create voice provider '{resolved_id}': {exc}",
            )

        if hasattr(provider, "model_dir"):
            try:
                model_dir = str(provider.model_dir)
            except Exception:  # noqa: BLE001
                pass

        try:
            voices = list(provider.list_voices())
        except ProviderError as exc:
            return VoiceDiscoveryResult(
                provider_id=getattr(provider, "provider_id", resolved_id),
                model_dir=model_dir,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return VoiceDiscoveryResult(
                provider_id=getattr(provider, "provider_id", resolved_id),
                model_dir=model_dir,
                error=f"Voice discovery failed: {exc}",
            )

        if not voices:
            detail = (
                f"Provider '{resolved_id}' returned an empty catalogue."
            )
            if resolved_id == PIPER_PROVIDER_ID and model_dir:
                detail += f" Place Piper *.onnx models in {model_dir}."
            elif model_dir:
                detail += (
                    f" Check model files under {model_dir} "
                    "(expected kokoro-v1.0.onnx and voices-v1.0.bin)."
                )
            return VoiceDiscoveryResult(
                provider_id=resolved_id,
                model_dir=model_dir,
                error=detail,
            )

        warning = ""
        filtered = voices
        if channel_language:
            filtered = [
                voice
                for voice in voices
                if voice_matches_language(voice.language, channel_language)
            ]
            if not filtered:
                warning = (
                    f"Found {len(voices)} voice(s), but none match channel "
                    f"language '{channel_language}'. Showing all voices so you "
                    "can still pick a narrator."
                )
                filtered = voices

        return VoiceDiscoveryResult(
            voices=filtered,
            provider_id=getattr(provider, "provider_id", resolved_id),
            model_dir=model_dir,
            warning=warning,
        )
