"""Tests for guided production stage detection."""

from __future__ import annotations

from pathlib import Path

from app.projects.production_stages import (
    StageState,
    VISIBLE_STAGES,
    scan_workflow,
)
from app.projects.project_intelligence import scan_project_progress


def test_visible_stages_order() -> None:
    keys = [s.key for s in VISIBLE_STAGES]
    assert keys == [
        "script",
        "production_sheet",
        "voice",
        "images",
        "movie",
        "shorts",
        "youtube_export",
    ]
    assert "thumbnail" not in keys


def test_empty_project_all_not_started(tmp_path: Path) -> None:
    snap = scan_workflow(tmp_path)
    assert snap.percent == 0
    assert snap.primary_action == "Generate Everything"
    assert all(s.state is StageState.NOT_STARTED for s in snap.stages)


def test_script_detects_completion(tmp_path: Path) -> None:
    script_dir = tmp_path / "script"
    script_dir.mkdir()
    (script_dir / "script.txt").write_text("Hello world narration.", encoding="utf-8")
    snap = scan_workflow(tmp_path)
    script = snap.stage("script")
    assert script is not None
    assert script.state is StageState.COMPLETED
    assert snap.primary_action == "Generate Sheet"
    assert snap.next_key == "production_sheet"


def test_scan_project_progress_compat(tmp_path: Path) -> None:
    progress = scan_project_progress(tmp_path)
    assert progress.percent_complete == 0
    assert [s.key for s in progress.steps] == [s.key for s in VISIBLE_STAGES]
