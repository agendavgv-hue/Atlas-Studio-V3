"""Tests for Phase 3.6 progress status UX."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.atlas_application import AtlasApplication
from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.projects.project_service import ProjectService
from app.projects.project_status import ProgressStep
from app.ui.branding.status_icons import status_icon_pixmap
from app.ui.pages.project_workspace_page import ProjectWorkspacePage


class StatusIconTests(unittest.TestCase):
    def test_icons_render_without_emoji(self) -> None:
        for state in ("complete", "missing", "running"):
            pixmap = status_icon_pixmap(state, 18)
            self.assertFalse(pixmap.isNull())
            self.assertEqual(pixmap.width(), 18)


class ProgressStepStateTests(unittest.TestCase):
    def test_states(self) -> None:
        self.assertEqual(
            ProgressStep("script", "Script", complete=True).state,
            "complete",
        )
        self.assertEqual(
            ProgressStep("movie", "Movie", complete=False).state,
            "missing",
        )
        self.assertEqual(
            ProgressStep("images", "Images", complete=False, running=True).state,
            "running",
        )


class WorkspaceUxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        existing = AtlasApplication.instance()
        if existing is None:
            cls.app = AtlasApplication(sys.argv[:1])
        else:
            cls.app = existing

    def test_workspace_shows_meta_without_idea(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            channel = "Hollow Atlas"
            project_root = root / "youtube"
            (project_root / channel).mkdir(parents=True)
            config = AppConfig(data_root=root / "atlas", project_root=project_root)
            Storage(config).ensure_structure()
            service = ProjectService(config)
            created = service.create_project(channel, "Atlantis", idea="should not show")

            old_projects = self.app.projects
            old_root = self.app.config.project_root
            try:
                self.app.config.project_root = project_root
                self.app.projects = service
                page = ProjectWorkspacePage()
                page.load_project(channel, created.folder_name)

                self.assertEqual(page._title.text(), created.folder_name)
                self.assertEqual(page._meta.text(), f"{channel} • Draft")
                self.assertNotIn("Idea", page._meta.text())
                self.assertNotIn("should not show", page._meta.text())
            finally:
                self.app.projects = old_projects
                self.app.config.project_root = old_root


if __name__ == "__main__":
    unittest.main()
