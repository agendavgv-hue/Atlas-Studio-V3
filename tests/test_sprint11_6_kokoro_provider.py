"""Unit tests for KokoroProvider ONNX backend (VoiceProvider only).

Uses a fake ``kokoro_onnx.Kokoro`` so CI does not require model downloads.
"""

from __future__ import annotations

import io
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.core.voice_settings import VoiceSettings
from app.providers.errors import ProviderError
from app.providers.kokoro import (
    KOKORO_MODEL_ID,
    KOKORO_PROVIDER_ID,
    KOKORO_SAMPLE_RATE,
    _HEALTH_CHECK_KEYS,
    KokoroProvider,
    _onnx_lang,
    _resolve_voice_id,
)
from app.providers.voice_base import VoiceSynthesisRequest


class _FakeKokoroEngine:
    def __init__(self, model_path: str, voices_path: str) -> None:
        self.model_path = model_path
        self.voices_path = voices_path
        self.calls: list[dict] = []

    def create(
        self,
        text: str,
        voice: str = "",
        speed: float = 1.0,
        lang: str = "en-us",
        **_kwargs,
    ):
        self.calls.append(
            {"text": text, "voice": voice, "speed": speed, "lang": lang}
        )
        samples = np.concatenate(
            [
                np.zeros(100, dtype=np.float32),
                np.ones(50, dtype=np.float32) * 0.25,
            ]
        )
        return samples, KOKORO_SAMPLE_RATE

    def get_voices(self) -> list[str]:
        return ["af_heart", "af_bella", "bf_emma"]


def _install_fake_kokoro_onnx(engine_cls=_FakeKokoroEngine):
    module = types.ModuleType("kokoro_onnx")
    module.Kokoro = engine_cls  # type: ignore[attr-defined]
    return patch.dict(sys.modules, {"kokoro_onnx": module})


class KokoroHelperTests(unittest.TestCase):
    def test_resolve_voice_id_defaults(self) -> None:
        self.assertEqual(_resolve_voice_id(""), "af_heart")
        self.assertEqual(_resolve_voice_id("local_default"), "af_heart")
        self.assertEqual(_resolve_voice_id("af_bella"), "af_bella")

    def test_onnx_lang_from_language_and_voice(self) -> None:
        self.assertEqual(_onnx_lang(voice_id="af_heart", language="en-US"), "en-us")
        self.assertEqual(_onnx_lang(voice_id="bf_emma", language="en-GB"), "en-gb")
        self.assertEqual(_onnx_lang(voice_id="bf_emma", language="en"), "en-gb")
        self.assertEqual(_onnx_lang(voice_id="af_heart", language=""), "en-us")


class KokoroProviderUnitTests(unittest.TestCase):
    def test_provider_id_and_empty_catalogue_without_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = KokoroProvider(
                VoiceSettings(),
                model_dir=Path(tmp),
                auto_download_models=False,
            )
            self.assertEqual(provider.provider_id, KOKORO_PROVIDER_ID)
            # Discovery requires a ready ONNX runtime — fail soft.
            voices = provider.list_voices()
            self.assertEqual(voices, [])
            self.assertEqual(provider.list_models(), [KOKORO_MODEL_ID])

    def test_list_voices_from_runtime_catalogue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kokoro-v1.0.onnx").write_bytes(b"fake-onnx")
            (root / "voices-v1.0.bin").write_bytes(b"fake-voices")
            provider = KokoroProvider(
                VoiceSettings(),
                model_dir=root,
                auto_download_models=False,
            )
            with _install_fake_kokoro_onnx():
                with patch.object(KokoroProvider, "_ensure_runtime", return_value=None):
                    voices = provider.list_voices()
            self.assertGreaterEqual(len(voices), 3)
            heart = next(v for v in voices if v.voice_id == "af_heart")
            self.assertEqual(heart.name, "Heart")
            self.assertEqual(heart.gender, "Female")
            self.assertEqual(heart.language, "en-US")
            self.assertTrue(heart.style_tags)

    def test_missing_runtime_raises_provider_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = KokoroProvider(
                VoiceSettings(),
                model_dir=Path(tmp),
                auto_download_models=False,
            )
            with patch.object(
                KokoroProvider,
                "_ensure_runtime",
                side_effect=ProviderError("missing"),
            ):
                with self.assertRaises(ProviderError):
                    provider.validate_ready()

    def test_missing_model_files_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = KokoroProvider(
                VoiceSettings(),
                model_dir=Path(tmp),
                auto_download_models=False,
            )
            with patch.object(KokoroProvider, "_ensure_runtime", return_value=None):
                with self.assertRaises(ProviderError) as raised:
                    provider.validate_ready()
            self.assertIn("model files", str(raised.exception).casefold())

    def test_synthesize_builds_wav_via_fake_onnx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kokoro-v1.0.onnx").write_bytes(b"fake-onnx")
            (root / "voices-v1.0.bin").write_bytes(b"fake-voices")
            settings = VoiceSettings(voice_id="af_heart", speed=1.2, language="en-US")
            provider = KokoroProvider(
                settings,
                model_dir=root,
                auto_download_models=False,
            )

            with _install_fake_kokoro_onnx():
                with patch.object(KokoroProvider, "_ensure_runtime", return_value=None):
                    result = provider.synthesize(
                        VoiceSynthesisRequest(
                            text="Hello Atlas.",
                            voice_id="af_heart",
                            speed=1.2,
                            language="en-US",
                            output_format="wav",
                        )
                    )

            self.assertEqual(result.content_type, "audio/wav")
            self.assertEqual(result.voice_id, "af_heart")
            self.assertEqual(result.model, KOKORO_MODEL_ID)
            self.assertTrue(result.audio_bytes.startswith(b"RIFF"))
            with wave.open(io.BytesIO(result.audio_bytes), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 1)
                self.assertEqual(wav.getframerate(), KOKORO_SAMPLE_RATE)
                self.assertEqual(wav.getnframes(), 150)

    def test_rejects_empty_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = KokoroProvider(
                VoiceSettings(),
                model_dir=Path(tmp),
                auto_download_models=False,
            )
            with self.assertRaises(ProviderError):
                provider.synthesize(VoiceSynthesisRequest(text="  "))

    def test_health_check_ok_with_fake_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kokoro-v1.0.onnx").write_bytes(b"fake-onnx")
            (root / "voices-v1.0.bin").write_bytes(b"fake-voices")
            provider = KokoroProvider(
                VoiceSettings(voice_id="af_heart", language="en-US"),
                model_dir=root,
                auto_download_models=False,
            )
            fake_ort = types.ModuleType("onnxruntime")
            fake_ort.__version__ = "1.20.1"  # type: ignore[attr-defined]

            with _install_fake_kokoro_onnx():
                with patch.dict(sys.modules, {"onnxruntime": fake_ort}):
                    health = provider.health_check()

            self.assertTrue(health.ok)
            self.assertEqual(health.provider_id, KOKORO_PROVIDER_ID)
            self.assertEqual(
                tuple(item.key for item in health.checks),
                _HEALTH_CHECK_KEYS,
            )
            for key in _HEALTH_CHECK_KEYS:
                item = health.check(key)
                self.assertIsNotNone(item)
                assert item is not None
                self.assertTrue(item.ok, msg=f"{key}: {item.message}")
            self.assertIn("healthy", health.message.casefold())
            self.assertGreaterEqual(health.elapsed_ms, 0.0)

    def test_health_check_reports_missing_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = KokoroProvider(
                VoiceSettings(),
                model_dir=Path(tmp),
                auto_download_models=False,
            )

            def fail_package(_self, checks):
                from app.providers.health import HealthCheckItem

                checks.append(
                    HealthCheckItem("kokoro_onnx", False, "Package missing.")
                )
                return False

            with patch.object(
                KokoroProvider,
                "_health_check_package",
                fail_package,
            ):
                health = provider.health_check()

            self.assertFalse(health.ok)
            package = health.check("kokoro_onnx")
            self.assertIsNotNone(package)
            assert package is not None
            self.assertFalse(package.ok)
            models = health.check("model_files")
            self.assertIsNotNone(models)
            assert models is not None
            self.assertFalse(models.ok)
            self.assertIn("Skipped", models.message)

    def test_health_check_reports_missing_model_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = KokoroProvider(
                VoiceSettings(),
                model_dir=Path(tmp),
                auto_download_models=False,
            )
            fake_ort = types.ModuleType("onnxruntime")
            fake_ort.__version__ = "1.20.1"  # type: ignore[attr-defined]

            with _install_fake_kokoro_onnx():
                with patch.dict(sys.modules, {"onnxruntime": fake_ort}):
                    health = provider.health_check()

            self.assertFalse(health.ok)
            models = health.check("model_files")
            self.assertIsNotNone(models)
            assert models is not None
            self.assertFalse(models.ok)
            synth = health.check("synthesis")
            self.assertIsNotNone(synth)
            assert synth is not None
            self.assertFalse(synth.ok)
            self.assertIn("Skipped", synth.message)

    def test_health_check_does_not_raise_on_synthesis_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kokoro-v1.0.onnx").write_bytes(b"fake-onnx")
            (root / "voices-v1.0.bin").write_bytes(b"fake-voices")
            provider = KokoroProvider(
                VoiceSettings(),
                model_dir=root,
                auto_download_models=False,
            )
            fake_ort = types.ModuleType("onnxruntime")
            fake_ort.__version__ = "1.20.1"  # type: ignore[attr-defined]

            class _BoomEngine(_FakeKokoroEngine):
                def create(self, *args, **kwargs):
                    raise RuntimeError("boom")

            with _install_fake_kokoro_onnx(_BoomEngine):
                with patch.dict(sys.modules, {"onnxruntime": fake_ort}):
                    health = provider.health_check()

            self.assertFalse(health.ok)
            synth = health.check("synthesis")
            self.assertIsNotNone(synth)
            assert synth is not None
            self.assertFalse(synth.ok)
            self.assertIn("boom", synth.message.casefold())

    def test_voice_pipeline_modules_remain_agnostic(self) -> None:
        import app.voice.generator as gen_mod
        import app.voice.service as svc_mod

        for mod in (gen_mod, svc_mod):
            text = Path(mod.__file__).read_text(encoding="utf-8")
            self.assertNotIn("kokoro_onnx", text)
            self.assertNotIn("KokoroProvider", text)


if __name__ == "__main__":
    unittest.main()
