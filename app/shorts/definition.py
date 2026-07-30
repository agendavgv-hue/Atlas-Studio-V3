"""ShortsDefinition — immutable plan for exactly one short.

The Generator renders this definition only; it never invents structure.
Every definition has a stable ``definition_id`` plus a 1-based ``index``.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


def new_definition_id() -> str:
    """Stable unique id for regeneration / editing / future AI optimization."""
    return str(uuid.uuid4())


@dataclass
class ShortsScene:
    """One visual beat inside a short."""

    index: int  # 1-based within this short
    image_path: str
    duration_sec: float
    motion: str = "none"
    transition: str = "cut"
    framing: str = "center_crop"
    sheet_ref: str = ""  # optional production-sheet anchor
    # Future: camera, effects, voice_span, subtitles
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShortsScene:
        raw = dict(data or {})
        return cls(
            index=int(raw.get("index") or 0),
            image_path=str(raw.get("image_path") or ""),
            duration_sec=float(raw.get("duration_sec") or 0.0),
            motion=str(raw.get("motion") or "none"),
            transition=str(raw.get("transition") or "cut"),
            framing=str(raw.get("framing") or "center_crop"),
            sheet_ref=str(raw.get("sheet_ref") or ""),
            extras=dict(raw.get("extras") or {}),
        )


@dataclass
class ShortsSegmentPlaceholder:
    """Reserved intro / outro / hook / CTA slot — empty until branding exists."""

    kind: str  # intro | outro | hook | cta
    enabled: bool = False
    duration_sec: float = 0.0
    asset_path: str | None = None
    text: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShortsSegmentPlaceholder:
        raw = dict(data or {})
        return cls(
            kind=str(raw.get("kind") or ""),
            enabled=bool(raw.get("enabled", False)),
            duration_sec=float(raw.get("duration_sec") or 0.0),
            asset_path=raw.get("asset_path"),
            text=str(raw.get("text") or ""),
            extras=dict(raw.get("extras") or {}),
        )


@dataclass
class ShortsVoicePlan:
    """Narration usage for this short."""

    use_voice: bool = False
    voice_path: str | None = None
    start_sec: float | None = None  # reserved clip window
    end_sec: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ShortsVoicePlan:
        raw = dict(data or {})
        return cls(
            use_voice=bool(raw.get("use_voice", False)),
            voice_path=raw.get("voice_path"),
            start_sec=(
                float(raw["start_sec"]) if raw.get("start_sec") is not None else None
            ),
            end_sec=float(raw["end_sec"]) if raw.get("end_sec") is not None else None,
        )


@dataclass
class ShortsOutputPlan:
    """Where this short lands and which profile snapshot applies."""

    filename: str = "short_01.mp4"
    folder: str = "short"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    profile: str = "shorts"
    codec: str = "libx264"
    preset: str = "medium"
    crf: int = 23

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ShortsOutputPlan:
        raw = dict(data or {})
        return cls(
            filename=str(raw.get("filename") or "short_01.mp4"),
            folder=str(raw.get("folder") or "short"),
            width=int(raw.get("width") or 1080),
            height=int(raw.get("height") or 1920),
            fps=int(raw.get("fps") or 30),
            profile=str(raw.get("profile") or "shorts"),
            codec=str(raw.get("codec") or "libx264"),
            preset=str(raw.get("preset") or "medium"),
            crf=int(raw.get("crf") or 23),
        )


@dataclass
class ShortsDefinition:
    """Complete recipe for one short. Stable ``definition_id`` never changes on regen of the same plan identity."""

    definition_id: str
    index: int  # 1-based export order / short_NN.mp4
    scenes: list[ShortsScene] = field(default_factory=list)
    timing_source: str = "default_per_image"
    total_duration_sec: float = 0.0
    voice: ShortsVoicePlan = field(default_factory=ShortsVoicePlan)
    output: ShortsOutputPlan = field(default_factory=ShortsOutputPlan)
    title: str = ""
    rationale: str = ""
    # Reserved planning placeholders (Planner may set enabled later).
    intro: ShortsSegmentPlaceholder = field(
        default_factory=lambda: ShortsSegmentPlaceholder(kind="intro")
    )
    outro: ShortsSegmentPlaceholder = field(
        default_factory=lambda: ShortsSegmentPlaceholder(kind="outro")
    )
    hook: ShortsSegmentPlaceholder = field(
        default_factory=lambda: ShortsSegmentPlaceholder(kind="hook")
    )
    cta: ShortsSegmentPlaceholder = field(
        default_factory=lambda: ShortsSegmentPlaceholder(kind="cta")
    )
    exported: bool = False
    export_path: str | None = None
    ai_score: float | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        index: int,
        scenes: list[ShortsScene] | None = None,
        definition_id: str | None = None,
        **kwargs: Any,
    ) -> ShortsDefinition:
        """Factory that always assigns a stable unique id when omitted."""
        return cls(
            definition_id=(definition_id or new_definition_id()).strip() or new_definition_id(),
            index=index,
            scenes=list(scenes or []),
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShortsDefinition:
        raw = dict(data or {})
        scenes = [
            ShortsScene.from_dict(item)
            for item in (raw.get("scenes") or [])
            if isinstance(item, dict)
        ]
        definition_id = str(raw.get("definition_id") or "").strip() or new_definition_id()
        ai_raw = raw.get("ai_score")
        try:
            ai_score = float(ai_raw) if ai_raw is not None else None
        except (TypeError, ValueError):
            ai_score = None
        return cls(
            definition_id=definition_id,
            index=max(1, int(raw.get("index") or 1)),
            scenes=scenes,
            timing_source=str(raw.get("timing_source") or "default_per_image"),
            total_duration_sec=float(raw.get("total_duration_sec") or 0.0),
            voice=ShortsVoicePlan.from_dict(
                raw.get("voice") if isinstance(raw.get("voice"), dict) else None
            ),
            output=ShortsOutputPlan.from_dict(
                raw.get("output") if isinstance(raw.get("output"), dict) else None
            ),
            title=str(raw.get("title") or ""),
            rationale=str(raw.get("rationale") or ""),
            intro=ShortsSegmentPlaceholder.from_dict(
                raw.get("intro") if isinstance(raw.get("intro"), dict) else {"kind": "intro"}
            ),
            outro=ShortsSegmentPlaceholder.from_dict(
                raw.get("outro") if isinstance(raw.get("outro"), dict) else {"kind": "outro"}
            ),
            hook=ShortsSegmentPlaceholder.from_dict(
                raw.get("hook") if isinstance(raw.get("hook"), dict) else {"kind": "hook"}
            ),
            cta=ShortsSegmentPlaceholder.from_dict(
                raw.get("cta") if isinstance(raw.get("cta"), dict) else {"kind": "cta"}
            ),
            exported=bool(raw.get("exported", False)),
            export_path=raw.get("export_path"),
            ai_score=ai_score,
            extras=dict(raw.get("extras") or {}),
        )
