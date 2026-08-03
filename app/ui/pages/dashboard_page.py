"""Dashboard — production overview and next step."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.atlas_application import AtlasApplication
from app.ui.branding.identity import VERSION, WINDOW_TITLE


class DashboardPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")

        subtitle = QLabel(f"{WINDOW_TITLE}  ·  Version {VERSION}")
        subtitle.setObjectName("PageSubtitle")

        welcome = QLabel("Your production desk")
        welcome.setObjectName("WelcomeTitle")

        self._message = QLabel(
            "Pick a channel studio, create a project, and produce. "
            "Each channel owns voice, AI, and style — projects inherit automatically."
        )
        self._message.setObjectName("PageSubtitle")
        self._message.setWordWrap(True)

        self._active = QLabel("")
        self._active.setObjectName("PageSubtitle")
        self._active.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        layout.addWidget(welcome)
        layout.addWidget(self._message)
        layout.addSpacing(16)
        layout.addWidget(self._active)
        layout.addStretch()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh_active()

    def _refresh_active(self) -> None:
        app = AtlasApplication.instance()
        if not isinstance(app, AtlasApplication):
            self._active.setText("")
            return
        channel = app.channels.active_channel_name
        if not channel:
            self._active.setText("Select a channel to begin.")
            return
        try:
            projects = app.projects.list_projects(channel)
        except Exception:  # noqa: BLE001
            self._active.setText(f"Channel: {channel}")
            return
        if not projects:
            self._active.setText(
                f"Channel: {channel}\nNo projects yet — create one under Projects."
            )
            return

        # Prefer the active project, else the most recently listed.
        active = app.projects.active_project
        project = None
        if active and active.channel_name == channel:
            for item in projects:
                if item.folder_name == active.folder_name:
                    project = item
                    break
        if project is None:
            project = projects[0]

        try:
            progress = app.projects.get_progress(channel, project.folder_name)
            status = app.projects.lifecycle_status(channel, project.folder_name)
        except Exception:  # noqa: BLE001
            self._active.setText(f"Channel: {channel}\nProject: {project.name}")
            return

        next_step = next((s.label for s in progress.steps if not s.complete), None)
        if next_step is None:
            guidance = "Production complete — ready to publish."
        else:
            guidance = f"Next step: {next_step}"

        lines = [
            f"Channel: {channel}",
            f"Project: {project.name}  ·  {status}  ·  {progress.percent_complete}%",
            guidance,
            "Open Projects → Open to continue in Project Details.",
        ]
        self._active.setText("\n".join(lines))
