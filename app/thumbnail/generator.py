"""ThumbnailGenerator — produce thumbnail image bytes only.

Provider-agnostic: talks only to ``ImageProvider``. Separate from the video
Image Generator pipeline — this module never reads production sheet prompts.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.errors import ProviderError
from app.providers.image_base import ImageGenerationRequest, ImageProvider
from app.thumbnail.prompt_builder import ThumbnailPromptPlan


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
    variant_id: str = ""


class ThumbnailGenerator:
    """Create thumbnail PNG bytes via the ImageProvider ABC only."""

    def __init__(self, provider: ImageProvider | None = None) -> None:
        self._provider = provider

    def generate_variant(self, plan: ThumbnailPromptPlan, *, settings) -> ThumbnailGenerationResult:
        if self._provider is None:
            raise ProviderError(
                "No image provider is configured for thumbnail generation."
            )
        if not (plan.prompt or "").strip():
            raise ProviderError("Thumbnail variant requires a non-empty prompt.")

        request = ImageGenerationRequest(
            prompt=plan.prompt,
            negative_prompt=plan.negative_prompt,
            width=int(getattr(settings, "width", 1280) or 1280),
            height=int(getattr(settings, "height", 720) or 720),
            steps=int(getattr(settings, "steps", 0) or 0),
            cfg_scale=float(getattr(settings, "cfg_scale", 0.0) or 0.0),
            sampler=str(getattr(settings, "sampler", "") or ""),
            seed=int(getattr(settings, "seed", -1) if getattr(settings, "seed", -1) is not None else -1),
            model=str(getattr(settings, "model", "") or ""),
        )
        response = self._provider.generate_image(request)
        if not response.image_png:
            raise ProviderError(
                f"Image provider returned an empty thumbnail for variant {plan.variant_id}."
            )
        return ThumbnailGenerationResult(
            image_png=response.image_png,
            provider_id=self._provider.provider_id,
            seed=response.seed,
            model=response.model,
            width=response.width,
            height=response.height,
            generation_time_ms=response.generation_time_ms,
            variant_id=plan.variant_id,
        )

    def generate(
        self,
        decision,
        request: ImageGenerationRequest | None,
        context,
    ) -> ThumbnailGenerationResult:
        """Legacy Sprint 9 entry point kept for selector-based unit tests."""
        del context
        from app.thumbnail.modes import ThumbnailMode

        if decision.mode in {ThumbnailMode.SELECT, ThumbnailMode.CANDIDATES}:
            return self.load_image_bytes(decision.source_image_path)
        return self._generate_via_provider(request)

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

    def load_image_bytes(self, path) -> ThumbnailGenerationResult:
        from pathlib import Path

        if path is None:
            raise ProviderError("Select mode requires a source image path.")
        file_path = Path(path)
        if not file_path.is_file():
            raise ProviderError(f"Selected thumbnail source is missing: {file_path}")
        try:
            payload = file_path.read_bytes()
        except OSError as exc:
            raise ProviderError(f"Cannot read selected thumbnail source: {exc}") from exc
        if not payload:
            raise ProviderError(f"Selected thumbnail source is empty: {file_path}")
        return ThumbnailGenerationResult(image_png=payload, provider_id="")
