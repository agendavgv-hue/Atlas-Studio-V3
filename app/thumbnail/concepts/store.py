"""Persist thumbnail_concepts.json."""

from __future__ import annotations

import json
from pathlib import Path

from app.thumbnail.concepts.models import ConceptBoard, ThumbnailConceptIdea
from app.thumbnail.naming import thumbnail_concepts_path


def write_concept_board(project_dir: Path, board: ConceptBoard) -> Path:
    path = thumbnail_concepts_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def read_concept_board(project_dir: Path) -> ConceptBoard | None:
    path = thumbnail_concepts_path(project_dir)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    concepts = [
        ThumbnailConceptIdea.from_dict(item, default_id=i)
        for i, item in enumerate(raw.get("concepts") or [], start=1)
        if isinstance(item, dict)
    ]
    return ConceptBoard(
        project_topic=str(raw.get("project_topic") or ""),
        channel_name=str(raw.get("channel_name") or ""),
        concepts=concepts,
        selected_id=int(raw.get("selected_id") or raw.get("chosen_concept_id") or 1),
        selected_reason=str(raw.get("selected_reason") or raw.get("chosen_reason") or ""),
        reference_analysis=dict(raw.get("reference_analysis") or {}),
        personality_focus=list(raw.get("personality_focus") or []),
        selected_scene=str(raw.get("selected_scene") or ""),
        click_value_reason=str(raw.get("click_value_reason") or ""),
        extras=dict(raw.get("extras") or {}),
    )
