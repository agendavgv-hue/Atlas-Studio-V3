"""AI Orchestrator + Creative Director tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.ai.factory import create_text_provider
from app.ai.orchestrator import AIOrchestratorService
from app.ai.roles import AIRole
from app.ai.settings import AIOrchestratorSettings, RoleBinding
from app.channels.models import Channel
from app.channels.studio.service import ChannelStudioService
from app.core.app_config import AppConfig
from app.creative.director import CreativeDirector
from app.creative.engine import CreativeDirectorEngine
from app.providers.base import TextProvider
from app.providers.errors import ProviderConfigurationError, ProviderError


class _FakeText(TextProvider):
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls = 0

    @property
    def provider_id(self) -> str:
        return "fake"

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        del system
        self.calls += 1
        return self.payload


class AIOrchestratorTests(unittest.TestCase):
    def test_role_bindings_and_fallback_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(data_root=root)
            config.ai = AIOrchestratorSettings.defaults()
            config.ai.roles[AIRole.CREATIVE_DIRECTOR.value] = RoleBinding(
                provider="ollama",
                model="qwen2.5:14b",
                fallback_provider="gemini",
                fallback_model="gemini-2.0-flash",
            )
            orch = AIOrchestratorService(config)
            routing = orch.describe_routing()
            self.assertEqual(routing["creative_director"]["provider"], "ollama")
            self.assertEqual(routing["image_generator"]["provider"], "forge")

    def test_create_ollama_provider_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(data_root=Path(tmp))
            config.ai = AIOrchestratorSettings.defaults()
            provider = create_text_provider(
                "qwen",
                config=config,
                model="qwen2.5:7b",
                ai_settings=config.ai,
            )
            self.assertEqual(provider.provider_id, "ollama")
            self.assertEqual(getattr(provider, "model"), "qwen2.5:7b")

    def test_creative_director_writes_artifacts_with_fake_llm(self) -> None:
        analysis_json = json.dumps(
            {
                "greatest_mystery": "Why ships vanish",
                "most_exciting_scene": "Whirlpool swallowing a schooner",
                "highest_ctr_image": "Giant compass over dark storm sea",
                "emotion": "mystery",
                "must_show_objects": ["compass", "ship"],
                "must_hide_objects": ["text", "logo"],
                "negative_space": "left",
                "title_placement": "left third",
                "logo_placement": "bottom_left",
                "dominant_colors": ["#0a1520", "#c9a227"],
                "composition": "rule_of_thirds",
                "camera_angle": "low_angle",
                "lighting": "storm rim light",
                "rationale": "Curiosity + scale",
            }
        )
        concepts_json = json.dumps(
            {
                "selected_scene": "Devil's Sea storm",
                "click_value_reason": "vanishing ships",
                "concepts": [
                    {
                        "id": i,
                        "title": f"HOOK {i}",
                        "foreground": "compass",
                        "midground": "ship",
                        "background": "storm",
                        "lighting": "rim",
                        "emotion": "mystery",
                        "elements": ["compass", "ship"],
                        "hero_subject": "compass",
                        "hook": f"HOOK {i}",
                    }
                    for i in range(1, 6)
                ],
            }
        )

        class _Seq(TextProvider):
            def __init__(self) -> None:
                self.n = 0

            @property
            def provider_id(self) -> str:
                return "fake"

            def generate_text(self, prompt: str, *, system: str | None = None) -> str:
                del system
                self.n += 1
                if "Analyze first" in prompt or "greatest_mystery" in prompt:
                    return analysis_json
                return concepts_json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            studio.ensure("Night Orchard", channel=Channel.create_default("Night Orchard"))
            brief = CreativeDirectorEngine(root).build_brief("Night Orchard")
            brief.project.topic = "The Devil's Sea"
            config = AppConfig(data_root=root)
            config.ai = AIOrchestratorSettings.defaults()
            orch = AIOrchestratorService(config)

            # Monkeypatch resolve_text to return fake provider.
            fake = _Seq()

            def _resolve(role):
                from app.ai.orchestrator import ResolvedAI

                return ResolvedAI(
                    role=AIRole.CREATIVE_DIRECTOR,
                    provider_id="fake",
                    model="fake-model",
                    provider=fake,
                    used_fallback=False,
                )

            orch.resolve_text = _resolve  # type: ignore[method-assign]
            project_dir = root / "proj"
            project_dir.mkdir()
            report = CreativeDirector(orch).direct_thumbnail(
                brief,
                script_text="Ships vanish in the Devil's Sea.",
                topic="The Devil's Sea",
                project_dir=project_dir,
            )
            self.assertEqual(report.analysis.emotion, "mystery")
            self.assertGreaterEqual(len(report.concepts.concepts), 5)
            thumb = project_dir / "thumbnail"
            self.assertTrue((thumb / "creative_director_report.json").is_file())
            self.assertTrue((thumb / "creative_brief.json").is_file())
            self.assertTrue((thumb / "thumbnail_concepts.json").is_file())


if __name__ == "__main__":
    unittest.main()
