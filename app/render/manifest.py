"""Render Manifest — durable plan for one Movie render.

Written as ``youtube_video/render_manifest.json`` beside ``video.mp4``.
Reserved fields support future Movie Engine upgrades without redesign.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.render.timeline import Timeline, TimelineScene


MANIFEST_VERSION = 1


@dataclass
class ManifestScene:
    """One visual beat. Effect/camera slots reserved for later sprints."""

    index: int
    image_path: str
    duration_sec: float
    motion: str
    transition: str = "fade"
    # Future Movie Engine hooks (unused in Sprint 8.1).
    camera: dict[str, Any] = field(default_factory=dict)
    effects: list[dict[str, Any]] = field(default_factory=list)
    voice_span: dict[str, Any] | None = None  # e.g. {start_sec, end_sec}
    subtitles: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_timeline_scene(cls, scene: TimelineScene) -> ManifestScene:
        return cls(
            index=scene.index,
            image_path=str(scene.image_path),
            duration_sec=float(scene.duration_sec),
            motion=scene.motion,
            transition=scene.transition,
        )


@dataclass
class ManifestSegment:
    """Intro / main / outro. Intro and outro stay empty until branding exists."""

    kind: str
    scenes: list[ManifestScene] = field(default_factory=list)


@dataclass
class ManifestAudio:
    """Narration + reserved music plan."""

    voice_path: str | None = None
    voice_duration_sec: float | None = None
    music_enabled: bool = False
    music_path: str | None = None
    music_volume: float = 0.15
    # Future: ducking, fade_in_sec, fade_out_sec, loop


@dataclass
class ManifestBranding:
    """Reserved branding assets — not applied in Sprint 8.1."""

    intro_path: str | None = None
    outro_path: str | None = None
    logo_path: str | None = None
    watermark_path: str | None = None


@dataclass
class ManifestOutput:
    """Where the render lands. Final filename stays ``video.mp4``."""

    folder: str = "youtube_video"
    video_filename: str = "video.mp4"
    keep_scene_renders: bool = False


@dataclass
class ManifestRenderSettings:
    """Snapshot of the profile used for this run."""

    profile: str = "youtube_hd"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    codec: str = "libx264"
    preset: str = "medium"
    crf: int = 23
    # Future: hwaccel, pixel_format overrides


@dataclass
class ManifestQuality:
    """Optional QC summary embedded in the manifest (no separate stats file)."""

    passed: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderManifest:
    """Complete durable plan for one movie render."""

    version: int = MANIFEST_VERSION
    duration_source: str = "default_per_image"
    total_duration_sec: float = 0.0
    segments: list[ManifestSegment] = field(default_factory=list)
    audio: ManifestAudio = field(default_factory=ManifestAudio)
    branding: ManifestBranding = field(default_factory=ManifestBranding)
    output: ManifestOutput = field(default_factory=ManifestOutput)
    render: ManifestRenderSettings = field(default_factory=ManifestRenderSettings)
    quality: ManifestQuality | None = None
    # Future top-level hooks (motion graphics layers, global parallax, etc.).
    layers: list[dict[str, Any]] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def main_scenes(self) -> list[ManifestScene]:
        for segment in self.segments:
            if segment.kind == "main":
                return list(segment.scenes)
        return []

    @classmethod
    def from_timeline(
        cls,
        timeline: Timeline,
        *,
        profile_id: str,
        width: int,
        height: int,
        fps: int,
        codec: str,
        preset: str,
        crf: int,
        keep_scene_renders: bool,
        voice_duration_sec: float | None = None,
        music_enabled: bool = False,
        music_volume: float = 0.15,
    ) -> RenderManifest:
        """Build a manifest from the current Timeline model."""
        segments: list[ManifestSegment] = []
        for segment in timeline.segments:
            segments.append(
                ManifestSegment(
                    kind=segment.kind,
                    scenes=[ManifestScene.from_timeline_scene(s) for s in segment.scenes],
                )
            )
        # Guarantee intro / main / outro keys exist for future branding.
        kinds = {item.kind for item in segments}
        for kind in ("intro", "main", "outro"):
            if kind not in kinds:
                segments.append(ManifestSegment(kind=kind, scenes=[]))
        segments.sort(key=lambda item: {"intro": 0, "main": 1, "outro": 2}.get(item.kind, 9))

        voice_path = str(timeline.voice_path) if timeline.voice_path else None
        music_path = str(timeline.music_path) if timeline.music_path else None
        return cls(
            duration_source=timeline.duration_source,
            total_duration_sec=float(timeline.total_duration_sec),
            segments=segments,
            audio=ManifestAudio(
                voice_path=voice_path,
                voice_duration_sec=voice_duration_sec,
                music_enabled=music_enabled,
                music_path=music_path,
                music_volume=music_volume,
            ),
            branding=ManifestBranding(),
            output=ManifestOutput(keep_scene_renders=keep_scene_renders),
            render=ManifestRenderSettings(
                profile=profile_id,
                width=width,
                height=height,
                fps=fps,
                codec=codec,
                preset=preset,
                crf=crf,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RenderManifest:
        """Best-effort load for tests/debug; unknown keys ignored via extras."""
        raw = dict(data or {})
        segments_raw = raw.get("segments") or []
        segments: list[ManifestSegment] = []
        for entry in segments_raw:
            if not isinstance(entry, dict):
                continue
            scenes: list[ManifestScene] = []
            for scene in entry.get("scenes") or []:
                if not isinstance(scene, dict):
                    continue
                scenes.append(
                    ManifestScene(
                        index=int(scene.get("index") or 0),
                        image_path=str(scene.get("image_path") or ""),
                        duration_sec=float(scene.get("duration_sec") or 0.0),
                        motion=str(scene.get("motion") or "none"),
                        transition=str(scene.get("transition") or "fade"),
                        camera=dict(scene.get("camera") or {}),
                        effects=list(scene.get("effects") or []),
                        voice_span=scene.get("voice_span"),
                        subtitles=list(scene.get("subtitles") or []),
                    )
                )
            segments.append(
                ManifestSegment(kind=str(entry.get("kind") or "main"), scenes=scenes)
            )

        audio_raw = raw.get("audio") if isinstance(raw.get("audio"), dict) else {}
        branding_raw = raw.get("branding") if isinstance(raw.get("branding"), dict) else {}
        output_raw = raw.get("output") if isinstance(raw.get("output"), dict) else {}
        render_raw = raw.get("render") if isinstance(raw.get("render"), dict) else {}
        quality_raw = raw.get("quality") if isinstance(raw.get("quality"), dict) else None

        quality = None
        if quality_raw is not None:
            quality = ManifestQuality(
                passed=bool(quality_raw.get("passed", True)),
                warnings=list(quality_raw.get("warnings") or []),
                errors=list(quality_raw.get("errors") or []),
                checks=dict(quality_raw.get("checks") or {}),
            )

        return cls(
            version=int(raw.get("version") or MANIFEST_VERSION),
            duration_source=str(raw.get("duration_source") or "default_per_image"),
            total_duration_sec=float(raw.get("total_duration_sec") or 0.0),
            segments=segments,
            audio=ManifestAudio(
                voice_path=audio_raw.get("voice_path"),
                voice_duration_sec=(
                    float(audio_raw["voice_duration_sec"])
                    if audio_raw.get("voice_duration_sec") is not None
                    else None
                ),
                music_enabled=bool(audio_raw.get("music_enabled", False)),
                music_path=audio_raw.get("music_path"),
                music_volume=float(audio_raw.get("music_volume") or 0.15),
            ),
            branding=ManifestBranding(
                intro_path=branding_raw.get("intro_path"),
                outro_path=branding_raw.get("outro_path"),
                logo_path=branding_raw.get("logo_path"),
                watermark_path=branding_raw.get("watermark_path"),
            ),
            output=ManifestOutput(
                folder=str(output_raw.get("folder") or "youtube_video"),
                video_filename=str(output_raw.get("video_filename") or "video.mp4"),
                keep_scene_renders=bool(output_raw.get("keep_scene_renders", False)),
            ),
            render=ManifestRenderSettings(
                profile=str(render_raw.get("profile") or "youtube_hd"),
                width=int(render_raw.get("width") or 1920),
                height=int(render_raw.get("height") or 1080),
                fps=int(render_raw.get("fps") or 30),
                codec=str(render_raw.get("codec") or "libx264"),
                preset=str(render_raw.get("preset") or "medium"),
                crf=int(render_raw.get("crf") or 23),
            ),
            quality=quality,
            layers=list(raw.get("layers") or []),
            extras=dict(raw.get("extras") or {}),
        )

    @classmethod
    def read_json(cls, path: Path) -> RenderManifest:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
