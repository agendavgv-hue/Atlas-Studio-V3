"""Channel Studio — Creative Director training UI with lazy tabs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.channels.studio.models import ChannelStudioPack
from app.channels.studio.service import ChannelStudioService
from app.channels.studio.training import evaluate_training
from app.core.project_root import ProjectRootError, is_project_root_configured
from app.ui.pages.channel_studio.lazy_host import LazySectionHost
from app.ui.pages.channel_studio.section_registry import (
    SECTION_SPECS,
    create_section_widget,
    section_spec,
)
from app.ui.pages.channel_studio.section_worker import (
    SectionLoadController,
    SectionLoadResult,
)
from app.ui.pages.channel_studio.training_card import TrainingCard
from app.ui.widgets.empty_state import EmptyState


class ChannelStudioPage(QWidget):
    """Shell opens instantly; each tab hydrates once and stays cached."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")
        self._folder: str | None = None
        self._pack: ChannelStudioPack | None = None
        self._service: ChannelStudioService | None = None
        self._loaded: set[str] = set()
        self._loading_section: str | None = None
        self._refs_wired: set[str] = set()
        self._picker_status_wired: set[str] = set()

        title = QLabel("Channel Studio")
        title.setObjectName("PageTitle")
        self._subtitle = QLabel("Train your AI Creative Director for this channel.")
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)

        self._basics = QLabel("")
        self._basics.setObjectName("PageSubtitle")
        self._basics.setWordWrap(True)

        self._training = TrainingCard()

        self._nav = QListWidget()
        self._nav.setObjectName("ChannelList")
        self._nav.setFixedWidth(220)
        self._stack = QStackedWidget()
        self._hosts: dict[str, LazySectionHost] = {}
        for spec in SECTION_SPECS:
            item = QListWidgetItem(spec.label)
            item.setData(Qt.ItemDataRole.UserRole, spec.key)
            item.setToolTip(spec.blurb)
            self._nav.addItem(item)
            host = LazySectionHost(spec.key, spec.label)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(host)
            self._stack.addWidget(scroll)
            self._hosts[spec.key] = host
        self._nav.currentRowChanged.connect(self._on_nav)

        self._loader = SectionLoadController(self)
        self._loader.section_ready.connect(self._on_section_ready)
        self._loader.section_failed.connect(self._on_section_failed)

        self._empty = EmptyState()
        self._editor = QWidget()
        editor_layout = QHBoxLayout(self._editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(16)
        editor_layout.addWidget(self._nav)
        editor_layout.addWidget(self._stack, stretch=1)

        save = QPushButton("Save Training")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._save)
        back = QPushButton("Back to Channels")
        back.clicked.connect(self._back_to_channels)
        actions = QHBoxLayout()
        actions.addWidget(save)
        actions.addWidget(back)
        actions.addStretch()

        self._status = QLabel("")
        self._status.setObjectName("PageSubtitle")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(self._subtitle)
        layout.addWidget(self._basics)
        layout.addWidget(self._training)
        layout.addWidget(self._editor, stretch=1)
        layout.addWidget(self._empty, stretch=1)
        layout.addLayout(actions)
        layout.addWidget(self._status)

        self._empty.hide()
        self._nav.blockSignals(True)
        self._nav.setCurrentRow(0)
        self._nav.blockSignals(False)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._folder and self._pack is not None:
            return
        self._try_active_channel()

    def load_channel(self, folder_name: str) -> None:
        """Open Channel Studio immediately with basics; tabs hydrate on demand."""
        app = self._app()
        if app is None:
            self._show_unavailable("Application is not ready.")
            return
        if not is_project_root_configured(app.config.project_root):
            self._empty.configure(
                "No Project Root",
                "Choose your YouTube library folder in Settings first.",
                "Open Settings",
                self._go_settings,
            )
            self._show_unavailable("Project Root is not set.")
            return

        if (
            self._folder == folder_name
            and self._pack is not None
            and "general" in self._loaded
        ):
            self._editor.show()
            self._empty.hide()
            self._refresh_training()
            self._status.setText("Continue training — open any studio tab.")
            return

        try:
            channel = app.channels.get_channel(folder_name)
        except (ProjectRootError, FileNotFoundError, OSError) as exc:
            self._show_unavailable(str(exc))
            return

        self._loader.cancel()
        self._reset_hosts()
        self._folder = channel.folder_name
        self._service = ChannelStudioService(Path(app.config.data_root))
        self._loaded.clear()
        self._loading_section = None
        self._refs_wired.clear()
        self._picker_status_wired.clear()

        self._subtitle.setText(f"Training Creative Director · {channel.name}")
        self._basics.setText(
            (channel.description or "No description yet.").strip() or "No description yet."
        )
        self._editor.show()
        self._empty.hide()
        self._status.setText("Loading channel basics…")
        self._nav.blockSignals(True)
        self._nav.setCurrentRow(0)
        self._nav.blockSignals(False)
        self._stack.setCurrentIndex(0)

        try:
            self._pack = self._service.load_basics(channel.folder_name, channel=channel)
        except OSError as exc:
            QMessageBox.warning(self, "Channel Studio", str(exc))
            return

        name = self._pack.general.name or channel.name
        self._subtitle.setText(f"Training Creative Director · {name}")
        self._basics.setText(
            (self._pack.general.description or channel.description or "No description yet.").strip()
        )
        self._refresh_training()
        self._status.setText("Ready — open a studio to continue training.")
        self._request_section("general")

    def _refresh_training(self) -> None:
        if self._pack is None:
            return
        # Apply open tabs so progress reflects unsaved edits.
        for key, host in self._hosts.items():
            content = host.content
            if content is not None and key in self._loaded:
                content.apply_pack(self._pack)
        progress = evaluate_training(self._pack, visited=self._loaded)
        self._training.update_progress(progress)
        # Mark nav items visually.
        for row in range(self._nav.count()):
            item = self._nav.item(row)
            key = str(item.data(Qt.ItemDataRole.UserRole) or "")
            label = next((s.label for s in SECTION_SPECS if s.key == key), key)
            if progress.completed.get(key):
                item.setText(f"✓  {label}")
            else:
                item.setText(label)

    def _reset_hosts(self) -> None:
        for host in self._hosts.values():
            host.clear_content()

    def _try_active_channel(self) -> None:
        app = self._app()
        if app is None:
            self._show_unavailable("Application is not ready.")
            return
        active = app.channels.active_channel_name
        if active:
            self.load_channel(active)
            return
        self._empty.configure(
            "No channel selected",
            "Open Channels, select a channel, then open Channel Studio to train its Creative Director.",
            "Open Channels",
            self._back_to_channels,
        )
        self._show_unavailable("Select a channel first.")

    def _on_nav(self, row: int) -> None:
        if row < 0:
            return
        self._stack.setCurrentIndex(row)
        item = self._nav.item(row)
        if item is None:
            return
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if key:
            self._request_section(key)

    def _request_section(self, key: str) -> None:
        if not self._folder or not self._service or self._pack is None:
            return
        host = self._hosts.get(key)
        if host is None:
            return
        if key in self._loaded and host.is_ready:
            self._refresh_training()
            return
        if self._loading_section == key:
            host.show_loading()
            return

        if self._loading_section and self._loading_section != key:
            previous = self._hosts.get(self._loading_section)
            if previous is not None and not previous.is_ready:
                previous.show_idle()

        host.show_loading()
        self._loading_section = key
        self._status.setText(f"Loading {host.label}…")

        spec = section_spec(key)
        if not spec.heavy:
            try:
                payload = self._service.load_section(self._folder, key)
                self._finish_section(key, payload)
            except Exception as exc:  # noqa: BLE001
                self._on_section_failed(key, str(exc))
            return

        self._loader.load(self._service.data_root, self._folder, key)

    def _on_section_ready(self, result: object) -> None:
        if not isinstance(result, SectionLoadResult):
            return
        if result.folder_name != self._folder:
            return
        self._finish_section(result.section, result.payload)

    def _finish_section(self, key: str, payload: object) -> None:
        if not self._service or self._pack is None:
            return
        host = self._hosts.get(key)
        if host is None:
            return
        try:
            self._service.apply_section(self._pack, key, payload)
            widget = host.content or create_section_widget(key)
            if host.content is None:
                host.set_content(widget)
            bind_assets = getattr(widget, "bind_assets", None)
            if callable(bind_assets) and self._folder and self._service:
                bind_assets(self._folder, self._service)
                if key not in self._picker_status_wired:
                    for picker in getattr(widget, "_asset_pickers", ()):
                        picker.status_message.connect(self._status.setText)
                        picker.changed.connect(lambda *_: self._refresh_training())
                    self._picker_status_wired.add(key)
            if key == "advanced":
                extra = payload if isinstance(payload, dict) else {}
                widget.load_pack(
                    self._pack,
                    root=str(extra.get("root") or ""),
                    counts=dict(extra.get("counts") or {}),
                )
            else:
                widget.load_pack(self._pack)
            self._bind_section_refs(key, widget)
        except Exception as exc:  # noqa: BLE001
            self._on_section_failed(key, str(exc))
            return

        self._loaded.add(key)
        self._loading_section = None
        self._status.setText(f"{host.label} ready.")
        self._refresh_training()

    def _bind_section_refs(self, key: str, widget: QWidget) -> None:
        if key in self._refs_wired or not self._service or not self._folder:
            return
        refs = getattr(widget, "refs", None)
        if refs is None:
            return
        refs.bind(self._folder, self._service)
        refs.status_message.connect(self._status.setText)
        if key == "thumbnail":
            style_dna = getattr(widget, "style_dna", None)
            if style_dna is not None:
                style_dna.bind(self._service.data_root, self._folder)

            def _on_thumb_refs_changed(
                *_args, folder=self._folder, service=self._service, card=style_dna
            ) -> None:
                try:
                    from app.thumbnail.style_dna.service import ThumbnailStyleDNAService

                    dna = ThumbnailStyleDNAService(service.data_root).ensure(
                        folder, force=True
                    )
                    if card is not None:
                        card.show_dna(dna)
                    self._status.setText(
                        f"Style DNA updated from {dna.reference_count} thumbnail reference(s)."
                    )
                except Exception as exc:  # noqa: BLE001
                    self._status.setText(f"Style DNA update failed: {exc}")

            refs.changed.connect(_on_thumb_refs_changed)
        self._refs_wired.add(key)

    def _on_section_failed(self, section: str, message: str) -> None:
        self._loading_section = None
        host = self._hosts.get(section)
        if host is not None and not host.is_ready:
            host.show_idle()
        self._status.setText(f"Failed to load {section}: {message}")

    def _save(self) -> None:
        app = self._app()
        if app is None or not self._pack or not self._service or not self._folder:
            return
        self._status.setText("Saving training…")
        for key, host in self._hosts.items():
            content = host.content
            if content is not None and key in self._loaded:
                content.apply_pack(self._pack)
        try:
            self._service.hydrate_missing(self._pack, self._loaded)
            channel = app.channels.get_channel(self._folder)
            self._service.save(self._pack, channel=channel)
            app.channels.save_channel(channel)
        except (ProjectRootError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Channel Studio", str(exc))
            self._status.setText("Save failed.")
            return
        self._refresh_training()
        self._status.setText(f"Training saved for {self._pack.general.name}")
        app.show_notification(
            "Creative Director Updated",
            self._pack.general.name or self._folder,
        )

    def _show_unavailable(self, message: str) -> None:
        self._editor.hide()
        self._empty.show()
        self._status.setText(message)
        self._subtitle.setText(message)
        self._basics.setText("")

    def _back_to_channels(self) -> None:
        window = self.window()
        show = getattr(window, "_show_page", None)
        if callable(show):
            show("channels")

    def _go_settings(self) -> None:
        window = self.window()
        show = getattr(window, "_show_page", None)
        if callable(show):
            show("settings")

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None
