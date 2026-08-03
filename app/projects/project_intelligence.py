"""Scan a project directory and report progress. No UI coupling."""

from __future__ import annotations

from pathlib import Path

from app.projects.production_stages import scan_workflow
from app.projects.project_status import ProgressStep, ProjectProgress


def scan_project_progress(project_dir: Path) -> ProjectProgress:
    """Analyse project folders and return completion for each progress step."""
    snapshot = scan_workflow(project_dir)
    steps = tuple(
        ProgressStep(
            key=stage.key,
            label=stage.label,
            complete=stage.complete,
            running=stage.state.value == "in_progress",
            failed=stage.state.value == "failed",
            detail=stage.detail,
        )
        for stage in snapshot.stages
    )
    return ProjectProgress(steps=steps)
