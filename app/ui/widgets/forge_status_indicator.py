"""Sidebar Forge status indicator — listens to ForgeStatusService only."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QWidget

from app.providers.backend_status import BackendStatus


class ForgeStatusIndicator(QWidget):
    """Compact live Forge status with tooltip and action menu."""

    # Backward-compatible: settings action (also emitted via action_requested).
    clicked = Signal()
    action_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ForgeStatusIndicator")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._status = BackendStatus.OFFLINE
        self._host = "127.0.0.1"
        self._port = 7860
        self._can_control_process = False
        self._has_launch_folder = False

        self._icon = QLabel("🔴")
        self._icon.setObjectName("ForgeStatusIcon")
        self._icon.setProperty("forgeState", "offline")

        self._dot = QLabel("●")
        self._dot.setObjectName("ForgeStatusDot")
        self._dot.setProperty("forgeState", "offline")

        self._text = QLabel("Forge Offline")
        self._text.setObjectName("ForgeStatusText")
        self._text.setProperty("forgeState", "offline")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._text, 1, Qt.AlignmentFlag.AlignVCenter)

        self.set_status(BackendStatus.OFFLINE)

    def set_connection_info(
        self,
        *,
        host: str,
        port: int,
        can_control_process: bool = False,
        has_launch_folder: bool = False,
    ) -> None:
        self._host = (host or "127.0.0.1").strip() or "127.0.0.1"
        try:
            self._port = int(port)
        except (TypeError, ValueError):
            self._port = 7860
        self._can_control_process = bool(can_control_process)
        self._has_launch_folder = bool(has_launch_folder)
        self._refresh_tooltip()

    def set_status(self, status: BackendStatus, message: str = "") -> None:
        self._status = status
        token = status.color_token
        self._icon.setText(status.emoji)
        self._icon.setProperty("forgeState", token)
        self._dot.setText(status.dot)
        self._dot.setProperty("forgeState", token)
        self._text.setProperty("forgeState", token)

        if message.strip():
            # Keep short sidebar labels; drop long diagnostic suffixes.
            label = message.strip()
            if "—" in label and status is BackendStatus.OFFLINE:
                label = BackendStatus.OFFLINE.display_title
        else:
            label = status.display_title
        self._text.setText(label)
        self._refresh_style(self._icon)
        self._refresh_style(self._dot)
        self._refresh_style(self._text)
        self._refresh_tooltip()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._show_menu(event.globalPosition().toPoint())
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def _refresh_tooltip(self) -> None:
        if self._status is BackendStatus.ONLINE:
            tip = (
                f"{BackendStatus.ONLINE.display_title}\n"
                f"Host: {self._host}\n"
                f"Port: {self._port}"
            )
        elif self._status is BackendStatus.STARTING:
            tip = BackendStatus.STARTING.display_title
        else:
            tip = BackendStatus.OFFLINE.display_title
        self.setToolTip(tip)

    def _show_menu(self, global_pos) -> None:
        menu = QMenu(self)
        menu.setObjectName("ForgeStatusMenu")

        if self._status is BackendStatus.ONLINE:
            self._add_action(menu, "Open Forge WebUI", "open_webui")
            restart = self._add_action(menu, "Restart Forge", "restart")
            restart.setEnabled(self._has_launch_folder or self._can_control_process)
            stop = self._add_action(menu, "Stop Forge", "stop")
            stop.setEnabled(self._can_control_process)
            folder = self._add_action(menu, "Open Forge Folder", "open_folder")
            folder.setEnabled(self._has_launch_folder)
            menu.addSeparator()
            self._add_action(menu, "Forge Settings", "settings")
        else:
            start = self._add_action(menu, "Start Forge", "start")
            start.setEnabled(
                self._status is not BackendStatus.STARTING and self._has_launch_folder
            )
            folder = self._add_action(menu, "Open Forge Folder", "open_folder")
            folder.setEnabled(self._has_launch_folder)
            menu.addSeparator()
            self._add_action(menu, "Forge Settings", "settings")

        menu.exec(global_pos)

    def _add_action(self, menu: QMenu, label: str, action_id: str) -> QAction:
        action = QAction(label, menu)

        def _emit(checked: bool = False, aid: str = action_id) -> None:
            del checked
            if aid == "settings":
                self.clicked.emit()
            self.action_requested.emit(aid)

        action.triggered.connect(_emit)
        menu.addAction(action)
        return action

    @staticmethod
    def _refresh_style(widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
