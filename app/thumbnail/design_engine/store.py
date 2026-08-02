"""Persist design_review.json."""

from __future__ import annotations

import json
from pathlib import Path

from app.thumbnail.design_engine.models import DesignReviewBoard, LayoutCandidate
from app.thumbnail.naming import resolve_thumbnail_dir

DESIGN_REVIEW_BASENAME = "design_review.json"


def design_review_path(project_dir: Path) -> Path:
    return resolve_thumbnail_dir(project_dir) / DESIGN_REVIEW_BASENAME


def write_design_review(project_dir: Path, board: DesignReviewBoard) -> Path:
    path = design_review_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def read_design_review(project_dir: Path) -> DesignReviewBoard | None:
    path = design_review_path(project_dir)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    layouts = []
    for item in raw.get("layouts") or []:
        if not isinstance(item, dict):
            continue
        from app.thumbnail.design_engine.models import DesignScores, RectNorm

        scores_raw = item.get("scores") if isinstance(item.get("scores"), dict) else {}
        scores = DesignScores(
            composition=float(scores_raw.get("composition") or scores_raw.get("Composition") or 0),
            brand_match=float(scores_raw.get("brand_match") or scores_raw.get("Brand Match") or 0),
            readability=float(scores_raw.get("readability") or scores_raw.get("Readability") or 0),
            ctr=float(scores_raw.get("ctr") or scores_raw.get("CTR") or 0),
            visual_balance=float(
                scores_raw.get("visual_balance") or scores_raw.get("Visual Balance") or 0
            ),
            negative_space=float(
                scores_raw.get("negative_space") or scores_raw.get("Negative Space") or 0
            ),
            professional_design=float(
                scores_raw.get("professional_design")
                or scores_raw.get("Professional Design")
                or 0
            ),
            overall=float(scores_raw.get("overall") or scores_raw.get("Overall") or item.get("Score") or 0),
            notes=[str(n) for n in (scores_raw.get("notes") or [])],
        )
        tr = item.get("text_rect") if isinstance(item.get("text_rect"), dict) else {}
        layouts.append(
            LayoutCandidate(
                id=str(item.get("id") or ""),
                label=str(item.get("label") or ""),
                text_anchor=str(item.get("text_anchor") or "left"),
                text_align=str(item.get("text_align") or "left"),
                max_lines=int(item.get("max_lines") or 3),
                title_scale=str(item.get("title_scale") or "large"),
                orientation=str(item.get("orientation") or "horizontal"),
                logo_position=str(item.get("logo_position") or "bottom_left"),
                logo_scale=float(item.get("logo_scale") or 0.11),
                top_ratio=float(item.get("top_ratio") or 0.12),
                max_width_ratio=float(item.get("max_width_ratio") or 0.4),
                margin_x_ratio=float(item.get("margin_x_ratio") or 0.05),
                lines=[str(x) for x in (item.get("lines") or [])],
                line_break_score=float(item.get("line_break_score") or 0),
                text_rect=RectNorm(
                    x=float(tr.get("x") or 0),
                    y=float(tr.get("y") or 0),
                    w=float(tr.get("w") or 0),
                    h=float(tr.get("h") or 0),
                ),
                scores=scores,
                image_relpath=str(item.get("image_relpath") or ""),
                why=str(item.get("why") or ""),
            )
        )
    return DesignReviewBoard(
        channel_name=str(raw.get("channel_name") or ""),
        project_name=str(raw.get("project_name") or ""),
        winner_id=str(raw.get("winner_id") or raw.get("Winnaar") or ""),
        winner_score=float(raw.get("winner_score") or 0),
        winner_why=str(raw.get("winner_why") or raw.get("Waarom") or ""),
        scene_map=dict(raw.get("scene_map") or {}),
        layouts=layouts,
        extras=dict(raw.get("extras") or {}),
    )
