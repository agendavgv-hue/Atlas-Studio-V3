"""Inline provider health presentation for Settings (no dialogs)."""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.health import ProviderHealth


@dataclass(frozen=True)
class VoiceHealthDisplay:
    """UI-facing voice provider health summary."""

    level: str  # ok | warn | error | busy | idle
    title: str
    detail: str = ""

    @property
    def indicator(self) -> str:
        return {
            "ok": "🟢",
            "warn": "🟡",
            "error": "🔴",
            "busy": "🟡",
            "idle": "⚪",
        }.get(self.level, "⚪")

    @property
    def headline(self) -> str:
        return f"{self.indicator} {self.title}"


def display_from_kokoro_health(health: ProviderHealth) -> VoiceHealthDisplay:
    """Map structured ProviderHealth to a calm inline status line."""
    package = health.check("kokoro_onnx")
    runtime = health.check("onnxruntime")
    models = health.check("model_files")
    synthesis = health.check("synthesis")

    if package is not None and not package.ok:
        return VoiceHealthDisplay(
            "error",
            "Package missing",
            "Install local voice deps with: pip install -r requirements-voice-local.txt",
        )
    if runtime is not None and not runtime.ok:
        return VoiceHealthDisplay(
            "error",
            "ONNX Runtime missing",
            "Install onnxruntime with: pip install -r requirements-voice-local.txt",
        )
    if models is not None and not models.ok:
        message = (models.message or "").casefold()
        if "download" in message or "failed to download" in message:
            return VoiceHealthDisplay(
                "warn",
                "Models not downloaded",
                "Kokoro models could not be downloaded. Check your network, then try again.",
            )
        return VoiceHealthDisplay(
            "warn",
            "Models not downloaded",
            "Kokoro models have not been downloaded yet.",
        )
    if synthesis is not None and not synthesis.ok:
        return VoiceHealthDisplay(
            "error",
            "Synthesis failed",
            synthesis.message or "Kokoro could not synthesize a test sentence.",
        )
    if health.ok:
        return VoiceHealthDisplay(
            "ok",
            "Kokoro Ready",
            "Local ONNX voice provider is healthy.",
        )
    return VoiceHealthDisplay(
        "error",
        "Not ready",
        health.message or "Kokoro health check failed.",
    )


def probe_kokoro_quick(*, model_dir) -> VoiceHealthDisplay:
    """Fast status without synthesis or downloads (for provider selection)."""
    from pathlib import Path

    try:
        from kokoro_onnx import Kokoro  # noqa: F401
    except Exception:  # noqa: BLE001
        return VoiceHealthDisplay(
            "error",
            "Package missing",
            "Install local voice deps with: pip install -r requirements-voice-local.txt",
        )
    try:
        import onnxruntime  # noqa: F401
    except Exception:  # noqa: BLE001
        return VoiceHealthDisplay(
            "error",
            "ONNX Runtime missing",
            "Install onnxruntime with: pip install -r requirements-voice-local.txt",
        )

    root = Path(model_dir)
    model_ok = (root / "kokoro-v1.0.onnx").is_file()
    voices_ok = (root / "voices-v1.0.bin").is_file()
    if not model_ok or not voices_ok:
        return VoiceHealthDisplay(
            "warn",
            "Models not downloaded",
            "Kokoro models have not been downloaded yet.",
        )
    return VoiceHealthDisplay(
        "ok",
        "Kokoro Ready",
        "Package, runtime, and model files look good. Use Test Provider to verify synthesis.",
    )
