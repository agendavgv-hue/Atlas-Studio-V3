"""Derive project lifecycle from Project Intelligence (presentation rules)."""

from __future__ import annotations

from app.projects.models import (
    STATUS_DRAFT,
    STATUS_IN_PROGRESS,
    STATUS_READY_TO_PUBLISH,
)
from app.projects.project_status import ProjectProgress


def derive_lifecycle_status(progress: ProjectProgress) -> str:
    """Classify a project from the highest completed production stage.

    Draft — no production stages completed yet (no script / no stages).
    In Progress — at least one production stage completed.
    Ready to Publish — finished video in youtube_video.
    Published — reserved for future manual status; never returned here.
    """
    youtube = progress.step("youtube_export")
    if youtube is not None and youtube.complete:
        return STATUS_READY_TO_PUBLISH

    if any(step.complete for step in progress.steps):
        return STATUS_IN_PROGRESS

    return STATUS_DRAFT
