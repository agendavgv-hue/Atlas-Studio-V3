"""Phase 3.5 tests — project template, numbering, and intelligence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.app_config import AppConfig
from app.core.storage import Storage
from app.projects.project_intelligence import scan_project_progress
from app.projects.project_numbering import (
    allocate_project_folder_name,
    next_project_number,
    parse_project_number,
    project_title,
)
from app.projects.project_service import ProjectService
from app.projects.project_template import PROJECT_TEMPLATE_FOLDERS, ensure_project_template


def _setup(tmp: Path) -> tuple[ProjectService, str, Path]:
    data_root = tmp / "atlas_data"
    project_root = tmp / "youtube"
    channel = "Hollow Atlas"
    (project_root / channel).mkdir(parents=True)
    config = AppConfig(data_root=data_root, project_root=project_root)
    Storage(config).ensure_structure()
    return ProjectService(config), channel, project_root


class ProjectTemplateTests(unittest.TestCase):
    def test_ensure_creates_all_standard_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "001 - Demo"
            ensure_project_template(project_dir)
            for name in PROJECT_TEMPLATE_FOLDERS:
                self.assertTrue((project_dir / name).is_dir(), msg=name)

    def test_create_project_applies_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, root = _setup(Path(tmp))
            project = service.create_project(channel, "Atlantis")
            project_dir = root / channel / project.folder_name
            for name in PROJECT_TEMPLATE_FOLDERS:
                self.assertTrue((project_dir / name).is_dir(), msg=name)

    def test_open_backfills_missing_template_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, root = _setup(Path(tmp))
            legacy = root / channel / "Legacy V2"
            legacy.mkdir()
            service.open_project(channel, "Legacy V2")
            for name in PROJECT_TEMPLATE_FOLDERS:
                self.assertTrue((legacy / name).is_dir(), msg=name)


class ProjectNumberingTests(unittest.TestCase):
    def test_parse_standard_numbered_names(self) -> None:
        self.assertEqual(parse_project_number("001 - Atlantis"), 1)
        self.assertEqual(parse_project_number("042 - Gobekli Tepe"), 42)
        self.assertIsNone(parse_project_number("Legacy Project"))
        self.assertIsNone(parse_project_number("2024 Recap"))
        self.assertEqual(project_title("001 - Atlantis"), "Atlantis")
        self.assertEqual(project_title("Legacy Project"), "Legacy Project")

    def test_next_number_from_existing(self) -> None:
        existing = ["001 - Atlantis", "002 - Gobekli Tepe", "Legacy"]
        self.assertEqual(next_project_number(existing), 3)

    def test_allocate_formats_with_padding(self) -> None:
        name = allocate_project_folder_name("Library of Alexandria", ["004 - Voynich"])
        self.assertEqual(name, "005 - Library of Alexandria")

    def test_service_assigns_sequential_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, _ = _setup(Path(tmp))
            first = service.create_project(channel, "Atlantis")
            second = service.create_project(channel, "Gobekli Tepe")
            self.assertEqual(first.folder_name, "001 - Atlantis")
            self.assertEqual(second.folder_name, "002 - Gobekli Tepe")


class ProjectIntelligenceTests(unittest.TestCase):
    def test_empty_project_all_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "001 - Empty"
            ensure_project_template(project_dir)
            progress = scan_project_progress(project_dir)
            self.assertTrue(all(not step.complete for step in progress.steps))

    def test_detects_files_in_standard_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "001 - Full"
            ensure_project_template(project_dir)
            (project_dir / "script" / "narration.txt").write_text("hello", encoding="utf-8")
            (project_dir / "script" / "production_sheet.csv").write_text("a,b\n", encoding="utf-8")
            (project_dir / "images" / "scene_01.png").write_bytes(b"fake")
            (project_dir / "insta" / "cover.jpg").write_bytes(b"fake")
            (project_dir / "mp4" / "final.mp4").write_bytes(b"fake")
            (project_dir / "short" / "short_01.mp4").write_bytes(b"fake")
            (project_dir / "thumbnail" / "thumb.png").write_bytes(b"fake")
            (project_dir / "youtube_video" / "upload.mp4").write_bytes(b"fake")

            progress = scan_project_progress(project_dir)
            by_key = {step.key: step.complete for step in progress.steps}
            self.assertTrue(by_key["script"])
            self.assertTrue(by_key["production_sheet"])
            self.assertTrue(by_key["images"])
            self.assertTrue(by_key["instagram"])
            self.assertTrue(by_key["movie"])
            self.assertTrue(by_key["shorts"])
            self.assertTrue(by_key["thumbnail"])
            self.assertTrue(by_key["youtube_export"])

    def test_images_tolerate_image_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "legacy"
            ensure_project_template(project_dir)
            legacy = project_dir / "image"
            legacy.mkdir(parents=True, exist_ok=True)
            (legacy / "old.png").write_bytes(b"fake")
            progress = scan_project_progress(project_dir)
            self.assertTrue(progress.step("images").complete)  # type: ignore[union-attr]

    def test_service_get_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, channel, root = _setup(Path(tmp))
            project = service.create_project(channel, "Scan Me")
            (root / channel / project.folder_name / "script" / "a.txt").write_text(
                "x", encoding="utf-8"
            )
            progress = service.get_progress(channel, project.folder_name)
            self.assertTrue(progress.step("script").complete)  # type: ignore[union-attr]
            self.assertFalse(progress.step("movie").complete)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
