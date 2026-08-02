"""Persist thumbnail_review.json + critic report artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from app.thumbnail.critic_engine.models import (
    CriticGroupScores,
    CriticReport,
    ImprovePlan,
    ReviewVersion,
    ThumbnailReviewBoard,
)
from app.thumbnail.naming import resolve_thumbnail_dir

THUMBNAIL_REVIEW_BASENAME = "thumbnail_review.json"
THUMBNAIL_CRITIC_REPORT_BASENAME = "thumbnail_critic_report.json"


def review_path(project_dir: Path) -> Path:
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_REVIEW_BASENAME


def critic_report_path(project_dir: Path) -> Path:
    return resolve_thumbnail_dir(project_dir) / THUMBNAIL_CRITIC_REPORT_BASENAME


def write_review_board(project_dir: Path, board: ThumbnailReviewBoard) -> Path:
    path = review_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def read_review_board(project_dir: Path) -> ThumbnailReviewBoard | None:
    path = review_path(project_dir)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None

    versions = []
    for item in raw.get("versions") or []:
        if not isinstance(item, dict):
            continue
        report = CriticReport.from_dict(item.get("report"))
        improve = ImprovePlan.from_dict(item.get("improve_plan"))
        versions.append(
            ReviewVersion(
                attempt=int(item.get("attempt") or 0),
                overall=float(item.get("overall") or item.get("Score") or 0),
                approved=bool(item.get("approved")),
                image_relpath=str(item.get("image_relpath") or ""),
                report=report,
                improve_plan=improve,
                prompt=str(item.get("prompt") or ""),
            )
        )
    groups_raw = raw.get("groups") if isinstance(raw.get("groups"), dict) else {}
    groups = CriticGroupScores(
        story=float(groups_raw.get("story") or groups_raw.get("Story") or 0),
        brand=float(groups_raw.get("brand") or groups_raw.get("Brand") or 0),
        layout=float(groups_raw.get("layout") or groups_raw.get("Layout") or 0),
        composition=float(
            groups_raw.get("composition") or groups_raw.get("Composition") or 0
        ),
        ctr=float(groups_raw.get("ctr") or groups_raw.get("CTR") or 0),
        curiosity=float(groups_raw.get("curiosity") or groups_raw.get("Curiosity") or 0),
        overall=float(groups_raw.get("overall") or groups_raw.get("Overall") or 0),
    )
    return ThumbnailReviewBoard(
        channel_name=str(raw.get("channel_name") or ""),
        project_name=str(raw.get("project_name") or ""),
        winner_attempt=int(raw.get("winner_attempt") or raw.get("Winnaar") or 1),
        winner_score=float(raw.get("winner_score") or 0),
        versions=versions,
        groups=groups,
        threshold=int(raw.get("threshold") or 90),
    )


def write_critic_report(project_dir: Path, report: CriticReport) -> Path:
    path = critic_report_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path
