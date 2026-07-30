"""ThumbnailGenerator — produce thumbnail image bytes only.

Provider-agnostic: talks only to ``ImageProvider`` (Provider Framework ABC).
Never selects sources, exports project files, or writes manifests.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.pipelines.context import PipelineContext
from app.providers.errors import ProviderError
from app.providers.image_base import ImageGenerationRequest, ImageProvider
from app.thumbnail.modes import ThumbnailMode
from app.thumbnail.selector import SelectionDecision


@dataclass(frozen=True)
class ThumbnailGenerationResult:
    """Generated (or loaded) image payload returned to ThumbnailService."""

    image_png: bytes
    provider_id: str = ""
    seed: int = -1
    model: str = ""
    width: int = 0
    height: int = 0
    generation_time_ms: float = 0.0


class ThumbnailGenerator:
    """Create thumbnail PNG bytes from a ``SelectionDecision``.

    For ``GENERATE``, requires a prepared ``ImageGenerationRequest`` and an
    ``ImageProvider``. The generator never constructs provider-specific APIs.
    """

    def __init__(self, provider: ImageProvider | None = None) -> None:
        self._provider = provider

    def generate(
        self,
        decision: SelectionDecision,
        request: ImageGenerationRequest | None,
        context: PipelineContext,
    ) -> ThumbnailGenerationResult:
        """Return PNG bytes for the service to export.

        ``context`` is accepted for pipeline consistency and future hooks;
        Sprint 9 generation uses ``decision`` + ``request`` + provider only.
        """
        del context  # reserved — keep signature stable for Service/Pipeline
        if decision.mode is ThumbnailMode.GENERATE:
            return self._generate_via_provider(request)
        return self._load_selected_image(decision)

    def _generate_via_provider(
        self,
        request: ImageGenerationRequest | None,
    ) -> ThumbnailGenerationResult:
        if self._provider is None:
            raise ProviderError(
                "No image provider is configured for thumbnail generation."
            )
        if request is None:
            raise ProviderError(
                "Generate mode requires a prepared ImageGenerationRequest."
            )
        if not (request.prompt or "").strip():
            raise ProviderError("Generate mode requires a non-empty prompt.")

        response = self._provider.generate_image(request)
        if not response.image_png:
            raise ProviderError("Image provider returned an empty thumbnail.")

        return ThumbnailGenerationResult(
            image_png=response.image_png,
            provider_id=self._provider.provider_id,
            seed=response.seed,
            model=response.model,
            width=response.width,
            height=response.height,
            generation_time_ms=response.generation_time_ms,
        )

    @staticmethod
    def _load_selected_image(decision: SelectionDecision) -> ThumbnailGenerationResult:
        path = decision.source_image_path
        if path is None:
            raise ProviderError("Select mode requires a source image path.")
        if not path.is_file():
            raise ProviderError(f"Selected thumbnail source is missing: {path}")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ProviderError(f"Cannot read selected thumbnail source: {exc}") from exc
        if not payload:
            raise ProviderError(f"Selected thumbnail source is empty: {path}")
        return ThumbnailGenerationResult(
            image_png=payload,
            provider_id="",
            seed=-1,
        )
