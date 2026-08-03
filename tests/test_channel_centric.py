"""Tests for channel-centric production profiles and project snapshots."""

from __future__ import annotations

from app.channels.models import Channel
from app.channels.production_profile import ChannelProductionProfile
from app.pipelines.context import ChannelDefaults
from app.projects.models import Project


def test_profile_round_trip_from_channel() -> None:
    channel = Channel.create_default("Night Orchard")
    channel.description = "Stories after dark"
    channel.outro_line = "Stay curious."
    channel.image_prompt = "cinematic night orchard"
    channel.voice = {
        "provider": "kokoro",
        "voice_id": "am_michael",
        "voice_name": "Michael",
        "style_tags": ["Deep", "Calm"],
    }
    channel.studio = {
        "ai_provider": "ollama",
        "ai_model": "qwen3:8b",
        "image_style": "warm gold",
        "resolution": "1920x1080",
        "brand_colors": {"primary": "#111", "accent": "#C9A227"},
    }
    profile = ChannelProductionProfile.from_channel(channel)
    assert profile.ai_provider == "ollama"
    assert profile.ai_model == "qwen3:8b"
    assert profile.image_style == "warm gold"
    assert profile.outro == "Stay curious."
    assert profile.brand_colors["accent"] == "#C9A227"

    restored = Channel.create_default("Night Orchard")
    profile.apply_to_channel(restored)
    assert restored.outro_line == "Stay curious."
    assert restored.studio["ai_model"] == "qwen3:8b"
    assert restored.voice["voice_id"] == "am_michael"


def test_project_snapshot_frozen() -> None:
    project = Project.create_default(name="01 - Test", channel_name="Night Orchard")
    assert project.channel_snapshot == {}
    project.channel_snapshot = {
        "channel_name": "Night Orchard",
        "ai_provider": "ollama",
        "ai_model": "old-model",
        "image_prompt": "frozen style",
        "outro_line": "frozen outro",
        "voice": {"voice_id": "am_michael"},
    }
    data = project.to_dict()
    loaded = Project.from_dict(
        data, fallback_name="01 - Test", fallback_channel="Night Orchard"
    )
    assert loaded.channel_snapshot["ai_model"] == "old-model"
    defaults = ChannelDefaults.from_mapping(loaded.channel_snapshot)
    assert defaults.outro_line == "frozen outro"
    assert defaults.image_prompt == "frozen style"


def test_defaults_from_profile_merge_style() -> None:
    profile = ChannelProductionProfile(
        channel_name="X",
        image_prompt="base",
        image_style="cinematic",
        prompt_template="documentary",
        outro="Bye",
    )
    defaults = ChannelDefaults.from_profile(profile)
    assert "cinematic" in defaults.image_prompt
    assert "documentary" in defaults.image_prompt
    assert defaults.outro_line == "Bye"
