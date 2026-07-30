"""VoiceGenerator — synthesize exactly what the VoiceManifest describes.

Provider-agnostic: talks only to ``VoiceProvider`` (Provider Framework ABC).
Never plans narration, rewrites text, splits/merges segment structure,
exports project files, or writes manifests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.pipelines.context import PipelineContext
from app.providers.errors import ProviderError
from app.providers.voice_base import (
    VoiceProvider,
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
)
from app.voice.manifest import VoiceManifest


@dataclass(frozen=True)
class VoiceGenerationResult:
    """Generated audio payload returned to VoiceService / VoiceExporter."""

    audio_bytes: bytes
    content_type: str = "audio/wav"
    provider_id: str = ""
    voice_id: str = ""
    model: str = ""
    generation_time_ms: float = 0.0


class VoiceGenerator:
    """Create narration audio bytes from a durable ``VoiceManifest``."""

    def generate(
        self,
        manifest: VoiceManifest,
        provider: VoiceProvider,
        context: PipelineContext,
    ) -> VoiceGenerationResult:
        """Synthesize audio for ``manifest`` via ``provider``.

        Builds ``VoiceSynthesisRequest`` exclusively from the manifest.
        ``context`` is accepted for pipeline consistency and future hooks.
        """
        del context  # reserved — keep signature stable for Service/Pipeline
        if provider is None:
            raise ProviderError("No voice provider is configured for generation.")

        request = self._request_from_manifest(manifest)
        response = provider.synthesize(request)
        return self._to_result(response, provider)

    @staticmethod
    def _request_from_manifest(manifest: VoiceManifest) -> VoiceSynthesisRequest:
        if not manifest.segments:
            raise ProviderError("VoiceManifest has no narration segments to synthesize.")

        # Consume segment text in order without rewriting or inventing segments.
        # Sprint 11 plans a single segment; full_text is the manifest's own join.
        text = manifest.full_text.strip()
        if not text:
            raise ProviderError("VoiceManifest narration text is empty.")

        output_format = _output_format_from_manifest(manifest)

        return VoiceSynthesisRequest(
            text=text,
            voice_id=str(manifest.voice_id or ""),
            language=str(manifest.language or ""),
            model=str(manifest.model or ""),
            stability=float(manifest.stability or 0.0),
            style=float(manifest.style or 0.0),
            speed=float(manifest.speed or 0.0),
            similarity=float(manifest.similarity or 0.0),
            output_format=output_format,
        )

    @staticmethod
    def _to_result(
        response: VoiceSynthesisResponse,
        provider: VoiceProvider,
    ) -> VoiceGenerationResult:
        if not response.audio_bytes:
            raise ProviderError("Voice provider returned empty audio.")
        return VoiceGenerationResult(
            audio_bytes=response.audio_bytes,
            content_type=str(response.content_type or "audio/wav"),
            provider_id=provider.provider_id,
            voice_id=str(response.voice_id or ""),
            model=str(response.model or ""),
            generation_time_ms=float(response.generation_time_ms or 0.0),
        )


def _output_format_from_manifest(manifest: VoiceManifest) -> str:
    """Derive provider output format from the manifest output filename only."""
    filename = str(manifest.output.filename or "").strip()
    if not filename:
        return ""
    suffix = Path(filename).suffix.lstrip(".").lower()
    return suffix
