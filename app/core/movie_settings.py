"""Movie / render settings — profiles, motion, timing, FFmpeg path."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Motion styles — per-scene when ``random``, else applied to every scene.
MOTION_STYLES = (
    "random",
    "zoom_in",
    "zoom_out",
    "pan_left",
    "pan_right",
    "none",
)

TRANSITION_STYLES = ("cut", "fade", "crossfade")

RENDER_PROFILE_IDS = (
    "youtube_hd",
    "youtube_4k",
    "shorts",
    "instagram",
    "custom",
)


@dataclass(frozen=True)
class RenderProfileSpec:
    profile_id: str
    label: str
    width: int
    height: int
    fps: int
    codec: str = "libx264"
    preset: str = "medium"
    crf: int = 23


RENDER_PROFILES: dict[str, RenderProfileSpec] = {
    "youtube_hd": RenderProfileSpec("youtube_hd", "YouTube HD", 1920, 1080, 30),
    "youtube_4k": RenderProfileSpec("youtube_4k", "YouTube 4K", 3840, 2160, 30, crf=20),
    "shorts": RenderProfileSpec("shorts", "Shorts", 1080, 1920, 30),
    "instagram": RenderProfileSpec("instagram", "Instagram", 1080, 1080, 30),
    "custom": RenderProfileSpec("custom", "Custom", 1920, 1080, 30),
}


@dataclass
class MovieSettings:
    """Persisted movie render configuration."""

    ffmpeg_path: str = ""
    profile: str = "youtube_hd"
    transition: str = "fade"
    motion: str = "random"
    default_duration_sec: float = 4.0
    width: int = 1920
    height: int = 1080
    fps: int = 30
    codec: str = "libx264"
    quality_preset: str = "medium"
    crf: int = 23
    keep_scene_renders: bool = False
    # Reserved for future music / branding (not used in Sprint 8).
    music_enabled: bool = False
    music_volume: float = 0.15

    def resolved_profile(self) -> RenderProfileSpec:
        key = (self.profile or "youtube_hd").strip().casefold()
        if key == "custom":
            return RenderProfileSpec(
                "custom",
                "Custom",
                max(16, int(self.width)),
                max(16, int(self.height)),
                max(1, int(self.fps)),
                codec=(self.codec or "libx264").strip() or "libx264",
                preset=(self.quality_preset or "medium").strip() or "medium",
                crf=max(0, int(self.crf)),
            )
        base = RENDER_PROFILES.get(key) or RENDER_PROFILES["youtube_hd"]
        return RenderProfileSpec(
            base.profile_id,
            base.label,
            base.width,
            base.height,
            base.fps,
            codec=(self.codec or base.codec).strip() or base.codec,
            preset=(self.quality_preset or base.preset).strip() or base.preset,
            crf=max(0, int(self.crf if self.crf else base.crf)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> MovieSettings:
        raw = data or {}
        profile = str(raw.get("profile") or "youtube_hd").strip().casefold() or "youtube_hd"
        if profile not in RENDER_PROFILE_IDS:
            profile = "youtube_hd"
        motion = str(raw.get("motion") or "random").strip().casefold() or "random"
        if motion not in MOTION_STYLES:
            motion = "random"
        transition = str(raw.get("transition") or "fade").strip().casefold() or "fade"
        if transition not in TRANSITION_STYLES:
            transition = "fade"
        return cls(
            ffmpeg_path=str(raw.get("ffmpeg_path") or "").strip(),
            profile=profile,
            transition=transition,
            motion=motion,
            default_duration_sec=max(0.5, _as_float(raw.get("default_duration_sec"), 4.0)),
            width=max(16, _as_int(raw.get("width"), 1920)),
            height=max(16, _as_int(raw.get("height"), 1080)),
            fps=max(1, _as_int(raw.get("fps"), 30)),
            codec=str(raw.get("codec") or "libx264").strip() or "libx264",
            quality_preset=str(raw.get("quality_preset") or "medium").strip() or "medium",
            crf=max(0, _as_int(raw.get("crf"), 23)),
            keep_scene_renders=bool(raw.get("keep_scene_renders", False)),
            music_enabled=bool(raw.get("music_enabled", False)),
            music_volume=_clamp(_as_float(raw.get("music_volume"), 0.15), 0.0, 1.0),
        )


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
