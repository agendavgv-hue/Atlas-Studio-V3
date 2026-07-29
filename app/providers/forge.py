"""Forge (A1111-compatible) image provider."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any

from app.core.forge_settings import ForgeSettings
from app.providers.errors import ProviderError
from app.providers.image_base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
)


class ForgeImageProvider(ImageProvider):
    def __init__(self, settings: ForgeSettings) -> None:
        self._settings = settings

    @property
    def provider_id(self) -> str:
        return "forge"

    @property
    def settings(self) -> ForgeSettings:
        return self._settings

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        settings = self._settings
        width = request.width if request.width > 0 else settings.width
        height = request.height if request.height > 0 else settings.height
        steps = request.steps if request.steps > 0 else settings.steps
        cfg = request.cfg_scale if request.cfg_scale > 0 else settings.cfg_scale
        sampler = (request.sampler or settings.sampler).strip()
        scheduler = (request.scheduler or settings.scheduler).strip()
        seed = request.seed if request.seed != -1 else settings.seed
        model = (request.model or settings.model).strip()
        negative = (
            request.negative_prompt
            if request.negative_prompt.strip()
            else settings.negative_prompt
        )

        if width <= 0 or height <= 0:
            raise ProviderError(
                "Image width and height must be configured in Image Provider settings."
            )

        payload: dict[str, Any] = {
            "prompt": request.prompt,
            "negative_prompt": negative,
            "steps": steps,
            "cfg_scale": cfg,
            "width": width,
            "height": height,
            "seed": seed,
            "sampler_name": sampler,
        }
        if scheduler:
            payload["scheduler"] = scheduler
        if model:
            payload["override_settings"] = {"sd_model_checkpoint": model}

        url = f"{settings.base_url}{settings.endpoint}"
        started = time.perf_counter()
        body = self._post_json(url, payload)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        images = body.get("images") or []
        if not images:
            raise ProviderError("Forge returned no images.")
        try:
            png = base64.b64decode(images[0])
        except (TypeError, ValueError) as exc:
            raise ProviderError("Forge returned an invalid image payload.") from exc

        info_seed = seed
        info = body.get("info")
        if isinstance(info, str):
            try:
                info_obj = json.loads(info)
                if isinstance(info_obj, dict) and "seed" in info_obj:
                    info_seed = int(info_obj["seed"])
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        return ImageGenerationResponse(
            image_png=png,
            seed=info_seed,
            model=model,
            sampler=sampler,
            steps=steps,
            cfg_scale=cfg,
            width=width,
            height=height,
            generation_time_ms=elapsed_ms,
        )

    def list_models(self) -> list[str]:
        url = f"{self._settings.base_url}/sdapi/v1/sd-models"
        body = self._get_json(url)
        if not isinstance(body, list):
            raise ProviderError("Unexpected Forge models response.")
        names: list[str] = []
        for entry in body:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title") or entry.get("model_name") or "").strip()
            if title:
                names.append(title)
        return sorted(dict.fromkeys(names))

    def test_connection(self) -> str:
        try:
            models = self.list_models()
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Forge is unreachable at {self._settings.base_url}: {exc}") from exc

        selected = (self._settings.model or "").strip()
        if not selected:
            return (
                f"Forge reachable at {self._settings.base_url} "
                f"({len(models)} model(s)). Select a model and save."
            )
        if selected not in models and not any(selected in name for name in models):
            raise ProviderError(
                f"Forge is reachable, but selected model '{selected}' was not found. "
                f"Available: {', '.join(models[:8])}{'…' if len(models) > 8 else ''}"
            )
        return f"Forge OK — model '{selected}' available ({len(models)} total)."

    def validate_ready(self) -> None:
        """Require Forge reachable and a selected model that exists."""
        try:
            models = self.list_models()
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Forge is unreachable at {self._settings.base_url}: {exc}"
            ) from exc

        selected = (self._settings.model or "").strip()
        if not selected:
            raise ProviderError(
                "No Forge model is selected. Open Settings, choose a model, and save."
            )
        if selected not in models and not any(selected in name for name in models):
            raise ProviderError(
                f"Selected Forge model '{selected}' was not found. "
                f"Available: {', '.join(models[:8])}{'…' if len(models) > 8 else ''}"
            )

    def _get_json(self, url: str) -> Any:
        request = urllib.request.Request(url, method="GET")
        return self._open_json(request)

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        body = self._open_json(request)
        if not isinstance(body, dict):
            raise ProviderError(f"Unexpected Forge response: {body}")
        return body

    def _open_json(self, request: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Forge HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(
                f"Forge network error ({self._settings.base_url}): {exc}"
            ) from exc
