"""ForgeStatusService — poll Forge API and manage optional process lifecycle.

The Sidebar must never call the Forge API directly; it only listens to signals
and requests actions through this service.
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from app.core.forge_settings import ForgeSettings
from app.providers.backend_status import BackendStatus


PROBE_INTERVAL_MS = 2000
PROBE_TIMEOUT_SEC = 1.5


class ForgeStatusService(QObject):
    """Polls Forge every 2s and optionally starts/stops a local Forge process."""

    status_changed = Signal(object)  # BackendStatus
    message_changed = Signal(str)

    def __init__(
        self,
        settings: ForgeSettings | None = None,
        *,
        parent: QObject | None = None,
        probe_interval_ms: int = PROBE_INTERVAL_MS,
    ) -> None:
        super().__init__(parent)
        self._settings = settings or ForgeSettings()
        self._status = BackendStatus.OFFLINE
        self._message = "Forge Offline"
        self._started_by_atlas = False
        self._process: subprocess.Popen | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(max(500, int(probe_interval_ms)))
        self._timer.timeout.connect(self._on_tick)

    @property
    def status(self) -> BackendStatus:
        return self._status

    @property
    def message(self) -> str:
        return self._message

    @property
    def started_by_atlas(self) -> bool:
        """True only when Atlas launched Forge during this session."""
        return self._started_by_atlas

    @property
    def settings(self) -> ForgeSettings:
        return self._settings

    @property
    def webui_url(self) -> str:
        return self._settings.base_url

    def update_settings(self, settings: ForgeSettings) -> None:
        self._settings = settings

    def tooltip_text(self) -> str:
        """Human-readable tooltip for the sidebar indicator."""
        if self._status is BackendStatus.ONLINE:
            return (
                f"{BackendStatus.ONLINE.display_title}\n"
                f"Host: {self._settings.host}\n"
                f"Port: {self._settings.port}"
            )
        if self._status is BackendStatus.STARTING:
            return BackendStatus.STARTING.display_title
        return BackendStatus.OFFLINE.display_title

    def start(self) -> None:
        """Begin polling. Call once after bootstrap."""
        if not self._timer.isActive():
            self._timer.start()
        self._on_tick()

    def stop_polling(self) -> None:
        self._timer.stop()

    def ensure_running_if_configured(self) -> None:
        """Honor auto_start_forge: start Forge only when offline and path is set."""
        if not self._settings.auto_start_forge:
            return
        if self.probe_online():
            self._set_status(BackendStatus.ONLINE, "Forge Online")
            return
        launch = (self._settings.launch_path or "").strip()
        if not launch:
            self._set_status(
                BackendStatus.OFFLINE,
                "Forge Offline — set Launch Path to auto-start",
            )
            return
        self.start_forge()

    def open_webui(self) -> bool:
        """Open the Forge WebUI in the default browser."""
        try:
            return bool(webbrowser.open(self.webui_url))
        except Exception:  # noqa: BLE001
            return False

    def open_forge_folder(self) -> bool:
        """Open the folder that contains the Forge launch script."""
        launch = (self._settings.launch_path or "").strip()
        if not launch:
            return False
        folder = Path(launch).expanduser().resolve().parent
        if not folder.is_dir():
            return False
        return _open_path(folder)

    def start_forge(self) -> bool:
        """Launch Forge if a launch path is configured. Marks started_by_atlas."""
        if self.probe_online():
            self._set_status(BackendStatus.ONLINE, "Forge Online")
            return True

        launch = (self._settings.launch_path or "").strip()
        if not launch:
            self._set_status(
                BackendStatus.OFFLINE,
                "Forge Offline — Launch Path not configured",
            )
            return False

        path = Path(launch).expanduser()
        if not path.is_file():
            self._set_status(
                BackendStatus.OFFLINE,
                f"Forge Offline — launch file missing: {path}",
            )
            return False

        self._set_status(BackendStatus.STARTING, "Starting Forge...")
        try:
            self._process = _spawn_forge(path)
            self._started_by_atlas = True
        except OSError as exc:
            self._process = None
            self._started_by_atlas = False
            self._set_status(BackendStatus.OFFLINE, f"Forge start failed: {exc}")
            return False
        return True

    def stop_forge(self) -> bool:
        """Stop Forge only if Atlas started it this session. Never kills external Forge."""
        if not self._started_by_atlas:
            return False
        proc = self._process
        self._process = None
        self._started_by_atlas = False
        if proc is not None:
            _terminate_process_tree(proc)
        if self.probe_online():
            self._set_status(BackendStatus.ONLINE, "Forge Online")
        else:
            self._set_status(BackendStatus.OFFLINE, "Forge Offline")
        return True

    def restart_forge(self) -> bool:
        """Restart Atlas-owned Forge, or start it if offline."""
        if self._started_by_atlas:
            self.stop_forge()
        return self.start_forge()

    def release_ownership(self) -> None:
        """Forget Atlas-owned process without killing it (user chose to leave Forge open)."""
        self._started_by_atlas = False
        self._process = None

    def probe_online(self) -> bool:
        """Return True when the Forge API answers."""
        return _probe_forge_api(self._settings.base_url)

    def _on_tick(self) -> None:
        online = self.probe_online()
        if online:
            self._set_status(BackendStatus.ONLINE, "Forge Online")
            return

        if self._status is BackendStatus.STARTING:
            if self._process is not None and self._process.poll() is not None:
                self._process = None
                self._started_by_atlas = False
                self._set_status(BackendStatus.OFFLINE, "Forge Offline — process exited")
            else:
                self._set_status(BackendStatus.STARTING, "Starting Forge...")
            return

        self._set_status(BackendStatus.OFFLINE, "Forge Offline")

    def _set_status(self, status: BackendStatus, message: str) -> None:
        changed = status is not self._status or message != self._message
        self._status = status
        self._message = message
        if changed:
            self.status_changed.emit(status)
            self.message_changed.emit(message)


def _open_path(path: Path) -> bool:
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
            return True
        subprocess.Popen(["xdg-open", str(path)])
        return True
    except OSError:
        return False


def _probe_forge_api(base_url: str) -> bool:
    root = (base_url or "").rstrip("/") or "http://127.0.0.1:7860"
    for path in ("/sdapi/v1/sd-models", "/"):
        url = f"{root}{path}"
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SEC) as response:
                code = getattr(response, "status", None) or response.getcode()
                if 200 <= int(code) < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
    return False


def _spawn_forge(path: Path) -> subprocess.Popen:
    cwd = str(path.parent)
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if path.suffix.casefold() in {".bat", ".cmd"}:
            return subprocess.Popen(
                f'"{path}"',
                cwd=cwd,
                shell=True,
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return subprocess.Popen(
            [str(path)],
            cwd=cwd,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return subprocess.Popen(
        [str(path)],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _terminate_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    pid = proc.pid
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass
