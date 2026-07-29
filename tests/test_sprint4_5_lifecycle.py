"""Sprint 4.5 — dynamic lifecycle from Project Intelligence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.projects.lifecycle import derive_lifecycle_status
from app.projects.models import (
    STATUS_DRAFT,
    STATUS_IN_PROGRESS,
    STATUS_READY_TO_PUBLISH,
)
from app.projects.project_intelligence import scan_project_progress
from app.projects.project_service import ProjectService
from app.projects.project_status import ProgressStep, ProjectProgress
from app.projects.project_template import ensure_project_template


class LifecycleDerivationTests(unittest.TestCase):
    def test_draft_when_nothing_complete(self) -> None:
        progress = ProjectProgress(
            steps=(ProgressStep("script", "Script", False),)
        )
        self.assertEqual(derive_lifecycle_status(progress), STATUS_DRAFT)

    def test_in_progress_when_any_stage_complete(self) -> None:
        progress = ProjectProgress(
            steps=(
                ProgressStep("script", "Script", True),
                ProgressStep("youtube_export", "YouTube Export", False),
            )
        )
        self.assertEqual(derive_lifecycle_status(progress), STATUS_IN_PROGRESS)

    def test_ready_when_youtube_export_complete(self) -> None:
        progress = ProjectProgress(
            steps=(
                ProgressStep("script", "Script", False),
                ProgressStep("youtube_export", "YouTube Export", True),
            )
        )
        self.assertEqual(derive_lifecycle_status(progress), STATUS_READY_TO_PUBLISH)

    def test_service_lifecycle_matches_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            channel = "Hollow Atlas"
            project_root = root / "yt"
            (project_root / channel).mkdir(parents=True)
            config = AppConfig(data_root=root / "atlas", project_root=project_root)
            Storage(config).ensure_structure()
            service = ProjectService(config)
            project = service.create_project(channel, "Atlantis")
            self.assertEqual(
                service.lifecycle_status(channel, project.folder_name),
                STATUS_DRAFT,
            )

            project_dir = project_root / channel / project.folder_name
            ensure_project_template(project_dir)
            (project_dir / "script" / "a.txt").write_text("x", encoding="utf-8")
            self.assertEqual(
                service.lifecycle_status(channel, project.folder_name),
                STATUS_IN_PROGRESS,
            )

            (project_dir / "youtube_video" / "final.mp4").write_bytes(b"fake")
            self.assertEqual(
                service.lifecycle_status(channel, project.folder_name),
                STATUS_READY_TO_PUBLISH,
            )
            # Sanity: scanner agrees
            scanned = scan_project_progress(project_dir)
            self.assertTrue(scanned.step("youtube_export").complete)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
