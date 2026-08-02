"""Persist scene_blueprint.json."""

from __future__ import annotations

import json
from pathlib import Path

from app.thumbnail.naming import SCENE_BLUEPRINT_BASENAME, resolve_thumbnail_dir
from app.thumbnail.scene_director.models import SceneBlueprint, SceneCandidate

__all__ = [
    "SCENE_BLUEPRINT_BASENAME",
    "read_scene_blueprint",
    "scene_blueprint_path",
    "write_scene_blueprint",
]


def scene_blueprint_path(project_dir: Path) -> Path:
    return resolve_thumbnail_dir(project_dir) / SCENE_BLUEPRINT_BASENAME


def write_scene_blueprint(project_dir: Path, blueprint: SceneBlueprint) -> Path:
    path = scene_blueprint_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blueprint.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def read_scene_blueprint(project_dir: Path) -> SceneBlueprint | None:
    path = scene_blueprint_path(project_dir)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    candidates = [
        SceneCandidate.from_dict(item, default_id=i)
        for i, item in enumerate(raw.get("candidates") or [], start=1)
        if isinstance(item, dict)
    ]
    return SceneBlueprint(
        main_subject=str(raw.get("main_subject") or raw.get("Main Subject") or ""),
        secondary_subject=str(
            raw.get("secondary_subject") or raw.get("Secondary Subject") or ""
        ),
        background=str(raw.get("background") or raw.get("Background") or ""),
        foreground=str(raw.get("foreground") or raw.get("Foreground") or ""),
        lighting=str(raw.get("lighting") or raw.get("Lighting") or "golden cinematic"),
        weather=str(raw.get("weather") or raw.get("Weather") or ""),
        composition=str(raw.get("composition") or raw.get("Composition") or "rule_of_thirds"),
        negative_space=str(raw.get("negative_space") or raw.get("Negative Space") or "left"),
        emotion=str(raw.get("emotion") or raw.get("Emotion") or "curiosity"),
        story=str(raw.get("story") or raw.get("Story") or ""),
        camera=str(raw.get("camera") or raw.get("Camera") or "eye_level"),
        lens=str(raw.get("lens") or raw.get("Lens") or "35mm cinematic"),
        depth=str(raw.get("depth") or raw.get("Depth") or ""),
        atmosphere=str(raw.get("atmosphere") or raw.get("Atmosphere") or ""),
        color_palette=[str(c) for c in (raw.get("color_palette") or raw.get("Color Palette") or [])],
        visual_focus=str(raw.get("visual_focus") or raw.get("Visual Focus") or ""),
        title=str(raw.get("title") or raw.get("Title") or ""),
        selected_scene_id=int(raw.get("selected_scene_id") or 1),
        selection_reason=str(
            raw.get("selection_reason") or raw.get("why_this_scene") or ""
        ),
        candidates=candidates,
        channel_name=str(raw.get("channel_name") or ""),
        project_topic=str(raw.get("project_topic") or ""),
        extras=dict(raw.get("extras") or {}),
    )
