"""Project application service — create, list, open, delete, rename."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass

from app.core.app_config import AppConfig
from app.core.project_root import ProjectRootError, require_project_root
from app.projects.models import Project
from app.projects.project_discovery import discover_project_folder_names
from app.projects.project_intelligence import scan_project_progress
from app.projects.project_numbering import allocate_project_folder_name
from app.projects.project_paths import ProjectPaths
from app.projects.project_status import ProjectProgress
from app.projects.project_store import ProjectStore
from app.projects.project_template import ensure_project_template

_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class ActiveProject:
    channel_name: str
    folder_name: str


class ProjectService:
    """Public project API. Depends on channel identity; Channels never call this."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._active: ActiveProject | None = None

    @property
    def active_project(self) -> ActiveProject | None:
        return self._active

    def _paths(self, channel_name: str) -> ProjectPaths:
        channel = channel_name.strip()
        if not channel:
            raise ValueError("Channel name is required for projects.")
        root = require_project_root(self._config.project_root)
        return ProjectPaths(root, channel)

    def list_projects(self, channel_name: str) -> list[Project]:
        try:
            paths = self._paths(channel_name)
        except ProjectRootError:
            return []

        if not paths.channel_dir.is_dir():
            return []

        store = ProjectStore(paths)
        projects: list[Project] = []
        for name in discover_project_folder_names(paths.channel_dir):
            project_dir = paths.project_dir(name)
            ensure_project_template(project_dir)
            projects.append(store.ensure_default(name))
        return projects

    def get_project(self, channel_name: str, name: str) -> Project:
        paths = self._paths(channel_name)
        folder = name.strip()
        project_dir = paths.project_dir(folder)
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Project folder not found: {folder}")
        ensure_project_template(project_dir)
        return ProjectStore(paths).ensure_default(folder)

    def create_project(
        self,
        channel_name: str,
        name: str,
        idea: str = "",
    ) -> Project:
        title = self._validate_name(name)
        paths = self._paths(channel_name)
        if not paths.channel_dir.is_dir():
            raise FileNotFoundError(
                f"Channel library folder not found: {channel_name.strip()}"
            )

        existing = discover_project_folder_names(paths.channel_dir)
        folder_name = allocate_project_folder_name(title, existing)
        store = ProjectStore(paths)
        project_dir = paths.project_dir(folder_name)

        if project_dir.exists() and store.exists(folder_name):
            ensure_project_template(project_dir)
            return store.load(folder_name)

        project_dir.mkdir(parents=True, exist_ok=True)
        ensure_project_template(project_dir)

        if store.exists(folder_name):
            return store.load(folder_name)

        project = Project.create_default(
            name=folder_name,
            channel_name=paths.channel_name,
            idea=idea.strip(),
        )
        store.save(project)
        return project

    def open_project(self, channel_name: str, name: str) -> Project:
        project = self.get_project(channel_name, name)
        self._active = ActiveProject(
            channel_name=project.channel_name,
            folder_name=project.folder_name,
        )
        return project

    def get_progress(self, channel_name: str, name: str) -> ProjectProgress:
        paths = self._paths(channel_name)
        folder = name.strip()
        project_dir = paths.project_dir(folder)
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Project folder not found: {folder}")
        return scan_project_progress(project_dir)

    def delete_project(self, channel_name: str, name: str) -> None:
        paths = self._paths(channel_name)
        folder = name.strip()
        project_dir = paths.project_dir(folder)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project folder not found: {folder}")
        shutil.rmtree(project_dir)
        if (
            self._active is not None
            and self._active.channel_name == paths.channel_name
            and self._active.folder_name == folder
        ):
            self._active = None

    def rename_project(self, channel_name: str, old_name: str, new_name: str) -> Project:
        """Architecture-only rename support (no dedicated UI in Phase 3)."""
        paths = self._paths(channel_name)
        old_folder = old_name.strip()
        new_folder = self._validate_name(new_name)
        old_dir = paths.project_dir(old_folder)
        new_dir = paths.project_dir(new_folder)

        if not old_dir.is_dir():
            raise FileNotFoundError(f"Project folder not found: {old_folder}")
        if new_dir.exists():
            raise FileExistsError(f"Project already exists: {new_folder}")

        store = ProjectStore(paths)
        project = store.ensure_default(old_folder)
        old_dir.rename(new_dir)
        ensure_project_template(new_dir)

        project.name = new_folder
        project.folder_name = new_folder
        ProjectStore(paths).save(project)

        if (
            self._active is not None
            and self._active.channel_name == paths.channel_name
            and self._active.folder_name == old_folder
        ):
            self._active = ActiveProject(
                channel_name=paths.channel_name,
                folder_name=new_folder,
            )
        return project

    def _validate_name(self, name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Project name cannot be empty.")
        if cleaned in {".", ".."}:
            raise ValueError("Project name is invalid.")
        if _INVALID_NAME.search(cleaned):
            raise ValueError("Project name contains invalid characters.")
        if cleaned.startswith("."):
            raise ValueError("Project name cannot start with a dot.")
        return cleaned
