"""Phase 3 tests — project system."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.projects.models import (
    STATUS_DRAFT,
    WORKFLOW_STEPS,
    Project,
    PROJECT_STATUSES,
)
from app.projects.project_service import ProjectService


def _setup(tmp: Path) -> tuple[ProjectService, str, Path]:
    data_root = tmp / "atlas_data"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    Storage(config).ensure_structure()
    return ProjectService(config), channel, project_root


class ProjectModelTests(unittest.TestCase):
    def test_default_status_is_draft(self) -> None:
        project = Project.create_default(name="Demo", channel_name="Ch")
        self.assertEqual(project.status, STATUS_DRAFT)

    def test_lifecycle_statuses_defined(self) -> None:
        self.assertEqual(
            list(PROJECT_STATUSES),
            ["Draft", "Ready", "In Progress", "Completed", "Archived"],
        )

    def test_workflow_steps_match_blueprint_order(self) -> None:
        self.assertEqual(
            list(WORKFLOW_STEPS),
            [
                "Idea",
                "Script",
                "Production Sheet",
                "Images",
                "Voice",
                "Movie",
                "Thumbnail",
                "SEO",
                "Export",
            ],
        )


class ProjectServiceTests(unittest.TestCase):
    def test_create_project_requires_channel_and_writes_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, root = _setup(Path(tmp))
            project = service.create_project(channel, "Episode 01", idea="A cold open")

            self.assertEqual(project.channel_name, channel)
            self.assertEqual(project.status, STATUS_DRAFT)
            self.assertEqual(project.idea, "A cold open")
            self.assertEqual(project.folder_name, "001 - Episode 01")
            project_dir = root / channel / "001 - Episode 01"
            self.assertTrue(project_dir.is_dir())
            config_path = project_dir / "project.json"
            self.assertTrue(config_path.is_file())
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "Draft")
            self.assertIn("script", payload)

    def test_list_discovers_existing_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, root = _setup(Path(tmp))
            (root / channel / "Legacy Project").mkdir()
            projects = service.list_projects(channel)
            self.assertEqual([p.name for p in projects], ["Legacy Project"])
            self.assertTrue((root / channel / "Legacy Project" / "project.json").is_file())

    def test_open_sets_active_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, _ = _setup(Path(tmp))
            created = service.create_project(channel, "Open Me")
            opened = service.open_project(channel, created.folder_name)
            self.assertEqual(opened.folder_name, "001 - Open Me")
            assert service.active_project is not None
            self.assertEqual(service.active_project.folder_name, "001 - Open Me")
            self.assertEqual(service.active_project.channel_name, channel)

    def test_delete_removes_project_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, root = _setup(Path(tmp))
            created = service.create_project(channel, "Temp")
            service.delete_project(channel, created.folder_name)
            self.assertFalse((root / channel / created.folder_name).exists())

    def test_rename_project_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, root = _setup(Path(tmp))
            created = service.create_project(channel, "Old Name", idea="idea")
            renamed = service.rename_project(channel, created.folder_name, "New Name")
            self.assertEqual(renamed.folder_name, "New Name")
            self.assertFalse((root / channel / created.folder_name).exists())
            self.assertTrue((root / channel / "New Name" / "project.json").is_file())

    def test_list_isolated_per_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, root = _setup(Path(tmp))
            other = "Mirror Drift"
            (root / other).mkdir()
            service.create_project(channel, "Only A")
            service.create_project(other, "Only B")
            self.assertEqual(
                [p.name for p in service.list_projects(channel)],
                ["001 - Only A"],
            )
            self.assertEqual(
                [p.name for p in service.list_projects(other)],
                ["001 - Only B"],
            )

    def test_create_without_channel_name_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = _setup(Path(tmp))
            with self.assertRaises(ValueError):
                service.create_project("  ", "Proj")


class DependencyDirectionTests(unittest.TestCase):
    def test_channels_do_not_import_projects(self) -> None:
        channel_dir = Path(__file__).resolve().parents[1] / "app" / "channels"
        for path in channel_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("app.projects", source, msg=str(path))

    def test_projects_do_not_import_channel_package(self) -> None:
        # Projects may use channel *names* only via service args — not channel modules.
        projects_dir = Path(__file__).resolve().parents[1] / "app" / "projects"
        for path in projects_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("app.channels", source, msg=str(path))


if __name__ == "__main__":
    unittest.main()
