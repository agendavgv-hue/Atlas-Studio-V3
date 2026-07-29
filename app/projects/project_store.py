"""Persist project.json under a project folder."""

from __future__ import annotations

import json
from pathlib import Path

from app.projects.models import Project
from app.projects.project_paths import ProjectPaths


class ProjectStore:
    """Load and save project configuration. No Channel mutation logic."""

    def __init__(self, paths: ProjectPaths) -> None:
        self._paths = paths

    def exists(self, folder_name: str) -> bool:
        return self._paths.config_file(folder_name).is_file()

    def load(self, folder_name: str) -> Project:
        path = self._paths.config_file(folder_name)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid project config: {path}")
        return Project.from_dict(
            raw,
            fallback_name=folder_name,
            fallback_channel=self._paths.channel_name,
        )

    def save(self, project: Project) -> Path:
        project_dir = self._paths.project_dir(project.folder_name)
        project_dir.mkdir(parents=True, exist_ok=True)
        path = self._paths.config_file(project.folder_name)
        path.write_text(
            json.dumps(project.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def ensure_default(self, folder_name: str) -> Project:
        if self.exists(folder_name):
            return self.load(folder_name)
        project = Project.create_default(
            name=folder_name,
            channel_name=self._paths.channel_name,
        )
        self.save(project)
        return project
