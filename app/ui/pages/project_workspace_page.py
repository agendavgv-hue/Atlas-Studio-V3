"""Project Details — guided production hub (workflow-first)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.atlas_application import AtlasApplication
from app.artifacts import ArtifactKind, ArtifactResolver
from app.pipelines.context import ChannelDefaults
from app.pipelines.image_naming import resolve_images_dir
from app.pipelines.image_progress import ImageQueueProgress
from app.pipelines.results import PipelineOutcome
from app.pipelines.voice_info import voice_file_info
from app.projects.assets.registry import AssetRegistry
from app.projects.production_stages import scan_workflow
from app.render.naming import final_video_path, resolve_youtube_dir
from app.render.progress import MovieQueueProgress
from app.ui.widgets.production_asset_card import ProductionAssetCard
from app.ui.widgets.voice_player import VoicePlayer
from app.ui.widgets.workflow_progress_panel import WorkflowProgressPanel
from app.voice.naming import resolve_voice_dir

_CARD_MIN_WIDTH = 300
_CARD_GAP = 16


class ProjectWorkspacePage(QWidget):
    """Production hub — guided next step + tracked production assets."""

    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageFrame")
        self._channel_name: str | None = None
        self._project_folder: str | None = None
        self._failed_keys: set[str] = set()
        self._card_columns = 0
        self._primary_stage_key: str | None = None
        self._asset_stage: dict[str, str] = {}

        back = QPushButton("← Back to Projects")
        back.setObjectName("SecondaryButton")
        back.clicked.connect(self.back_requested.emit)

        self._title = QLabel("Project")
        self._title.setObjectName("PageTitle")

        self._meta = QLabel("")
        self._meta.setObjectName("PageSubtitle")
        self._meta.setWordWrap(True)

        self._primary = QPushButton("Generate Everything")
        self._primary.setObjectName("PrimaryButton")
        self._primary.setMinimumHeight(52)
        self._primary.clicked.connect(self._on_primary_clicked)

        self._cancel = QPushButton("Cancel")
        self._cancel.setObjectName("SecondaryButton")
        self._cancel.setEnabled(False)
        self._cancel.clicked.connect(self._cancel_generate_everything)

        primary_row = QHBoxLayout()
        primary_row.setSpacing(12)
        primary_row.addWidget(self._primary, stretch=1)
        primary_row.addWidget(self._cancel)

        self._progress_panel = WorkflowProgressPanel()

        self._status_line = QLabel("")
        self._status_line.setObjectName("PageSubtitle")
        self._status_line.setWordWrap(True)

        assets_label = QLabel("Production Assets")
        assets_label.setObjectName("SectionLabel")

        self._cards: dict[str, ProductionAssetCard] = {}
        self._cards_host = QWidget()
        self._cards_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._cards_grid = QGridLayout(self._cards_host)
        self._cards_grid.setContentsMargins(0, 0, 0, 0)
        self._cards_grid.setHorizontalSpacing(_CARD_GAP)
        self._cards_grid.setVerticalSpacing(_CARD_GAP)

        self._voice_player = VoicePlayer()
        self._voice_info = QLabel("")
        self._voice_info.setObjectName("PageSubtitle")

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(36, 28, 36, 36)
        body_layout.setSpacing(18)
        body_layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
        body_layout.addWidget(self._title)
        body_layout.addWidget(self._meta)
        body_layout.addSpacing(4)
        body_layout.addLayout(primary_row)
        body_layout.addWidget(self._progress_panel)
        body_layout.addWidget(self._status_line)
        body_layout.addWidget(assets_label)
        body_layout.addWidget(self._cards_host)
        body_layout.addWidget(self._voice_info)
        body_layout.addWidget(self._voice_player)
        body_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._connect_tasks()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load_project(self, channel_name: str, project_folder: str) -> None:
        self._voice_player.stop()
        self._channel_name = channel_name
        self._project_folder = project_folder
        self._failed_keys.clear()
        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._relayout_cards(force=True)
        self.refresh()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout_cards()

    def refresh(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        try:
            project = app.projects.get_project(self._channel_name, self._project_folder)
            project_dir = app.projects.project_dir(
                self._channel_name, self._project_folder
            )
            status = app.projects.lifecycle_status(
                self._channel_name, self._project_folder
            )
        except (OSError, FileNotFoundError, ValueError):
            self._title.setText("Project not found")
            self._meta.setText("")
            return

        self._title.setText(project.name)
        idea = (project.idea or "").strip()
        meta = f"{project.channel_name}  ·  {status}"
        if idea:
            meta = f"{meta}\n{idea}"
        self._meta.setText(meta)

        running = self._running_stage_keys()
        snapshot = scan_workflow(
            project_dir,
            running_keys=running,
            failed_keys=self._failed_keys,
        )
        self._primary_stage_key = snapshot.primary_stage_key
        self._progress_panel.apply_snapshot(snapshot)

        busy = self._is_busy()
        # load() seeds + disk-reconciles only when assets.json is empty.
        catalog = AssetRegistry(project_dir).load()
        self._rebuild_asset_cards(catalog.visible_assets(), busy=busy)

        if snapshot.primary_action == "Production Complete":
            self._primary.setText("Production Complete")
            self._primary.setEnabled(False)
        else:
            self._primary.setText(snapshot.primary_action)
            self._primary.setEnabled(not busy or self._is_generation_for_project())

        one_click = self._is_generation_for_project() and bool(
            app and app.generation.is_running
        )
        if one_click:
            self._primary.setText("Continue Production")
            self._primary.setEnabled(False)
        self._cancel.setEnabled(one_click)

        self._refresh_voice_panel()

    # ------------------------------------------------------------------
    # Primary CTA
    # ------------------------------------------------------------------

    def _on_primary_clicked(self) -> None:
        label = self._primary.text()
        if label in {"Generate Everything", "Continue Production"}:
            self._start_generate_everything()
            return
        key = self._primary_stage_key
        if key:
            self._run_stage(key, regenerate=False)
        else:
            self._start_generate_everything()

    # ------------------------------------------------------------------
    # Card actions
    # ------------------------------------------------------------------

    def _rebuild_asset_cards(self, assets, *, busy: bool) -> None:
        wanted = {a.id for a in assets}
        for asset_id in list(self._cards.keys()):
            if asset_id not in wanted:
                card = self._cards.pop(asset_id)
                card.setParent(None)
                card.deleteLater()
                self._asset_stage.pop(asset_id, None)

        for asset in assets:
            card = self._cards.get(asset.id)
            if card is None:
                card = ProductionAssetCard()
                card.generate_clicked.connect(self._on_asset_generate)
                card.regenerate_clicked.connect(self._on_asset_regenerate)
                card.open_clicked.connect(self._on_asset_open)
                card.reveal_clicked.connect(self._on_asset_reveal)
                self._cards[asset.id] = card
            self._asset_stage[asset.id] = asset.stage_key
            card.apply_asset(asset, busy=busy)

        self._relayout_cards(force=True)

    def _on_asset_generate(self, asset_id: str) -> None:
        stage = self._asset_stage.get(asset_id)
        if stage:
            self._on_card_generate(stage)

    def _on_asset_regenerate(self, asset_id: str) -> None:
        stage = self._asset_stage.get(asset_id)
        if stage:
            self._on_card_regenerate(stage)

    def _on_asset_open(self, asset_id: str) -> None:
        root = self._project_dir()
        if root is None:
            return
        catalog = AssetRegistry(root).load()
        asset = catalog.get(asset_id)
        if asset is None or not asset.location:
            QMessageBox.information(self, "Atlas Studio", "Asset file not found yet.")
            return
        path = root / asset.location
        if not path.exists():
            QMessageBox.information(self, "Atlas Studio", f"Missing:\n{path}")
            return
        self._open_path(path)

    def _on_asset_reveal(self, asset_id: str) -> None:
        root = self._project_dir()
        if root is None:
            return
        catalog = AssetRegistry(root).load()
        asset = catalog.get(asset_id)
        if asset is None or not asset.location:
            QMessageBox.information(self, "Atlas Studio", "No folder yet.")
            return
        path = root / asset.location
        folder = path if path.is_dir() else path.parent
        folder.mkdir(parents=True, exist_ok=True)
        self._open_path(folder)

    def _on_card_generate(self, key: str) -> None:
        app = self._app()
        if app is None:
            return
        # Stop long-running stages when card shows Stop.
        if key == "images" and app.tasks.is_images_running and self._is_active_job():
            app.tasks.stop_images()
            self._status_line.setText("Stopping images…")
            return
        if key == "voice" and app.tasks.is_voice_running and self._is_active_job():
            app.tasks.stop_voice()
            self._status_line.setText("Stopping voice…")
            return
        if key == "movie" and app.tasks.is_movie_running and self._is_active_job():
            app.tasks.stop_movie()
            self._status_line.setText("Stopping movie…")
            return
        if key == "shorts" and app.tasks.is_shorts_running and self._is_active_job():
            app.tasks.stop_shorts()
            self._status_line.setText("Stopping shorts…")
            return
        self._run_stage(key, regenerate=False)

    def _on_card_regenerate(self, key: str) -> None:
        self._run_stage(key, regenerate=True)

    def _on_card_open(self, key: str) -> None:
        openers = {
            "script": lambda: self._open_artifact(ArtifactKind.SCRIPT),
            "production_sheet": lambda: self._open_artifact(ArtifactKind.PRODUCTION_SHEET),
            "voice": self._open_voice_folder,
            "images": self._open_images_folder,
            "movie": self._open_movie_folder,
            "shorts": self._open_shorts_folder,
            "youtube_export": self._open_export_folder,
        }
        fn = openers.get(key)
        if fn:
            fn()

    def _on_card_preview(self, key: str) -> None:
        if key == "voice":
            path = self._resolve_voice_path()
            if path is None:
                QMessageBox.information(self, "Atlas Studio", "No voice file yet.")
                return
            self._voice_player.set_source(path)
            self._voice_player.play()
            return
        if key == "movie":
            self._open_movie_video()
            return
        if key == "shorts":
            self._open_shorts_preview()
            return

    def _run_stage(self, key: str, *, regenerate: bool) -> None:
        self._failed_keys.discard(key)
        runners = {
            "script": self._run_script,
            "production_sheet": self._run_sheet,
            "voice": self._start_voice,
            "images": self._start_images,
            "movie": self._start_movie,
            "shorts": self._start_shorts,
            "youtube_export": self._start_export,
        }
        fn = runners.get(key)
        if fn is None:
            return
        root = self._project_dir()
        if root is not None:
            pipeline_id = {
                "script": "script",
                "production_sheet": "production_sheet",
                "voice": "voice",
                "images": "images",
                "movie": "movie",
                "shorts": "shorts",
                "youtube_export": "export",
            }.get(key, key)
            try:
                AssetRegistry(root).mark_pipeline_started(pipeline_id)
            except Exception:  # noqa: BLE001
                pass
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            self._failed_keys.add(key)
            QMessageBox.warning(self, "Atlas Studio", str(exc))
            self.refresh()
            return
        _ = regenerate
        self.refresh()

    # ------------------------------------------------------------------
    # Stage runners
    # ------------------------------------------------------------------

    def _run_script(self) -> None:
        app = self._app()
        if app is None:
            return
        self._status_line.setText("Generating script…")
        app.processEvents()
        result = app.production.regenerate_script(self._context())
        self._apply_result("script", result)

    def _run_sheet(self) -> None:
        app = self._app()
        if app is None:
            return
        self._status_line.setText("Generating production sheet…")
        app.processEvents()
        result = app.production.regenerate_production_sheet(self._context())
        self._apply_result("production_sheet", result)

    def _start_images(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.tasks.is_busy:
            QMessageBox.information(self, "Atlas Studio", "A job is already running.")
            return
        started = app.tasks.start_images(
            app.production,
            self._context(),
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            raise RuntimeError("Could not start image generation.")
        self._status_line.setText("Generating images…")

    def _start_voice(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.tasks.is_busy:
            QMessageBox.information(self, "Atlas Studio", "A job is already running.")
            return
        started = app.tasks.start_voice(
            app.production,
            self._context(),
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            raise RuntimeError("Could not start voice generation.")
        self._status_line.setText("Generating voice-over…")

    def _start_movie(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.tasks.is_busy:
            QMessageBox.information(self, "Atlas Studio", "A job is already running.")
            return
        started = app.tasks.start_movie(
            app.production,
            self._context(),
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            raise RuntimeError("Could not start movie render.")
        self._status_line.setText("Rendering movie…")

    def _start_shorts(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.tasks.is_busy:
            QMessageBox.information(self, "Atlas Studio", "A job is already running.")
            return
        from app.shorts.settings import ShortsSettings

        started = app.tasks.start_shorts(
            app.production,
            self._context(),
            settings=ShortsSettings(
                max_shorts=2,
                max_duration_sec=30.0,
                min_duration_sec=20.0,
                independent_creative=True,
            ),
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            raise RuntimeError("Could not start shorts generation.")
        self._status_line.setText("Generating shorts…")

    def _start_export(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.tasks.is_busy:
            QMessageBox.information(self, "Atlas Studio", "A job is already running.")
            return
        from app.projects.assets.registry import AssetRegistry
        from app.tasks.instagram_export import verify_youtube_export

        project_dir = app.projects.project_dir(self._channel_name, self._project_folder)

        def work():
            result = verify_youtube_export(project_dir)
            try:
                AssetRegistry(project_dir).record_pipeline_result("export", result)
            except Exception:  # noqa: BLE001
                pass
            return result

        started = app.tasks.start_export(
            work,
            engine=app.production,
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            raise RuntimeError("Could not start export verification.")
        self._status_line.setText("Preparing export package…")

    def _start_generate_everything(self) -> None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return
        if app.generation.is_running or app.tasks.is_busy:
            self._status_line.setText("A production job is already running.")
            return
        started = app.generation.start(
            app.production,
            self._context(),
            channel_name=self._channel_name,
            project_folder=self._project_folder,
        )
        if not started:
            self._status_line.setText("Could not start production.")
            return
        self._voice_player.stop()
        self._failed_keys.clear()
        self._status_line.setText("Running full production workflow…")
        self.refresh()

    def _cancel_generate_everything(self) -> None:
        app = self._app()
        if app is None:
            return
        if app.generation.is_running and self._is_generation_for_project():
            app.generation.cancel()
            self._status_line.setText("Cancelling after current task…")
            self.refresh()

    # ------------------------------------------------------------------
    # Task signals
    # ------------------------------------------------------------------

    def _connect_tasks(self) -> None:
        app = self._app()
        if app is None:
            return
        app.tasks.image_progress.connect(self._on_image_progress)
        app.tasks.image_finished.connect(lambda r: self._on_job_finished("images", r))
        app.tasks.image_running_changed.connect(lambda *_: self.refresh())
        app.tasks.voice_progress.connect(self._on_voice_progress)
        app.tasks.voice_finished.connect(lambda r: self._on_job_finished("voice", r))
        app.tasks.voice_running_changed.connect(lambda *_: self.refresh())
        app.tasks.movie_progress.connect(self._on_movie_progress)
        app.tasks.movie_finished.connect(lambda r: self._on_job_finished("movie", r))
        app.tasks.movie_running_changed.connect(lambda *_: self.refresh())
        app.tasks.shorts_finished.connect(lambda r: self._on_job_finished("shorts", r))
        app.tasks.shorts_running_changed.connect(lambda *_: self.refresh())
        app.tasks.export_finished.connect(
            lambda r: self._on_job_finished("youtube_export", r)
        )
        app.tasks.export_running_changed.connect(lambda *_: self.refresh())
        app.generation.running_changed.connect(lambda *_: self.refresh())
        app.generation.log_line.connect(self._on_generation_log)
        app.generation.finished.connect(self._on_generation_finished)

    def _on_generation_log(self, line: str) -> None:
        if self._is_generation_for_project():
            self._status_line.setText(line)

    def _on_generation_finished(self, result) -> None:
        if self._channel_name and self._project_folder:
            self._apply_result(None, result)
            self.refresh()

    def _on_job_finished(self, key: str, result) -> None:
        if self._is_generation_for_project():
            return
        self._apply_result(key, result)
        self.refresh()

    def _on_image_progress(self, progress: ImageQueueProgress) -> None:
        if self._is_generation_for_project() or not self._is_active_job():
            return
        self._status_line.setText(
            f"Images  {progress.completed}/{progress.total}  ·  {progress.message}"
        )

    def _on_voice_progress(self, progress) -> None:
        if self._is_generation_for_project() or not self._is_active_job():
            return
        message = getattr(progress, "message", "") or "Generating voice…"
        self._status_line.setText(str(message))

    def _on_movie_progress(self, progress: MovieQueueProgress) -> None:
        if self._is_generation_for_project() or not self._is_active_job():
            return
        self._status_line.setText(progress.message or "Rendering movie…")

    def _apply_result(self, key: str | None, result) -> None:
        outcome = getattr(result, "outcome", None)
        message = str(getattr(result, "message", "") or "")
        if outcome == PipelineOutcome.FAILED and key:
            self._failed_keys.add(key)
            self._status_line.setText(message or f"{key} failed")
        elif outcome == PipelineOutcome.CANCELLED:
            self._status_line.setText(message or "Cancelled")
        else:
            if key:
                self._failed_keys.discard(key)
            self._status_line.setText(message or "Done")

    # ------------------------------------------------------------------
    # Paths / open helpers
    # ------------------------------------------------------------------

    def _context(self):
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            raise RuntimeError("Project is not open.")
        project = app.projects.get_project(self._channel_name, self._project_folder)
        # Prefer frozen snapshot; soft-migrate older projects once.
        try:
            channel = app.channels.get_channel(self._channel_name)
            live = channel.production_profile().to_dict()
            if not project.channel_snapshot:
                project = app.projects.ensure_channel_snapshot(
                    self._channel_name,
                    self._project_folder,
                    live,
                )
            defaults = ChannelDefaults.from_mapping(
                project.channel_snapshot or live,
                name=channel.name,
            )
        except (OSError, FileNotFoundError, ValueError):
            defaults = ChannelDefaults(
                name=self._channel_name,
            )
            if project.channel_snapshot:
                defaults = ChannelDefaults.from_mapping(
                    project.channel_snapshot, name=self._channel_name
                )
        return app.production.build_context(project, defaults)

    def _project_dir(self) -> Path | None:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return None
        return app.projects.project_dir(self._channel_name, self._project_folder)

    def _open_artifact(self, kind: ArtifactKind) -> None:
        root = self._project_dir()
        if root is None:
            return
        resolver = ArtifactResolver(root)
        path = resolver.find(kind) if hasattr(resolver, "find") else None
        if path is None and hasattr(resolver, "open_path"):
            path = resolver.open_path(kind)
        if path is None or not Path(path).exists():
            QMessageBox.information(self, "Atlas Studio", "File not found yet.")
            return
        self._open_path(Path(path))

    def _open_images_folder(self) -> None:
        root = self._project_dir()
        if root is None:
            return
        self._open_path(resolve_images_dir(root))

    def _open_voice_folder(self) -> None:
        root = self._project_dir()
        if root is None:
            return
        self._open_path(resolve_voice_dir(root))

    def _open_movie_folder(self) -> None:
        root = self._project_dir()
        if root is None:
            return
        folder = root / "mp4"
        folder.mkdir(parents=True, exist_ok=True)
        self._open_path(folder)

    def _open_movie_video(self) -> None:
        root = self._project_dir()
        if root is None:
            return
        path = final_video_path(root)
        if not path.is_file():
            # Fall back to first mp4 scene
            mp4 = root / "mp4"
            videos = sorted(mp4.glob("*.mp4")) if mp4.is_dir() else []
            if not videos:
                QMessageBox.information(self, "Atlas Studio", "No movie file yet.")
                return
            path = videos[0]
        self._open_path(path)

    def _open_shorts_folder(self) -> None:
        root = self._project_dir()
        if root is None:
            return
        folder = root / "short"
        folder.mkdir(parents=True, exist_ok=True)
        self._open_path(folder)

    def _open_shorts_preview(self) -> None:
        root = self._project_dir()
        if root is None:
            return
        folder = root / "short"
        videos = sorted(folder.glob("*.mp4")) if folder.is_dir() else []
        if not videos:
            QMessageBox.information(self, "Atlas Studio", "No shorts yet.")
            return
        self._open_path(videos[0])

    def _open_export_folder(self) -> None:
        root = self._project_dir()
        if root is None:
            return
        self._open_path(resolve_youtube_dir(root))

    def _open_path(self, path: Path) -> None:
        path = path.expanduser().resolve()
        if not path.exists():
            QMessageBox.information(self, "Atlas Studio", f"Path not found:\n{path}")
            return
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _resolve_voice_path(self) -> Path | None:
        root = self._project_dir()
        if root is None:
            return None
        return ArtifactResolver(root).resolve(ArtifactKind.VOICE)

    def _refresh_voice_panel(self) -> None:
        path = self._resolve_voice_path()
        if path is None:
            self._voice_info.setText("")
            self._voice_player.set_source(None)
            return
        info = voice_file_info(path, duration_ms=self._voice_player.duration_ms or None)
        if info is None:
            self._voice_info.setText("")
            self._voice_player.set_source(None)
            return
        self._voice_info.setText(f"Voice preview  ·  {info.summary}")
        self._voice_player.set_source(path)

    # ------------------------------------------------------------------
    # Busy / running helpers
    # ------------------------------------------------------------------

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None

    def _is_busy(self) -> bool:
        app = self._app()
        return bool(app and (app.tasks.is_busy or app.generation.is_running))

    def _is_active_job(self) -> bool:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return False
        return app.tasks.is_job_for(self._channel_name, self._project_folder)

    def _is_generation_for_project(self) -> bool:
        app = self._app()
        if app is None or not self._channel_name or not self._project_folder:
            return False
        return app.generation.is_job_for(self._channel_name, self._project_folder)

    def _running_stage_keys(self) -> set[str]:
        app = self._app()
        keys: set[str] = set()
        if app is None:
            return keys
        if app.generation.is_running and self._is_generation_for_project():
            # Mark next incomplete as in-progress during one-click.
            root = self._project_dir()
            if root is not None:
                snap = scan_workflow(root, failed_keys=self._failed_keys)
                if snap.next_key:
                    keys.add(snap.next_key)
            return keys
        if not self._is_active_job():
            return keys
        if app.tasks.is_images_running:
            keys.add("images")
        if app.tasks.is_voice_running:
            keys.add("voice")
        if app.tasks.is_movie_running:
            keys.add("movie")
        if app.tasks.is_shorts_running:
            keys.add("shorts")
        if getattr(app.tasks, "is_export_running", False):
            keys.add("youtube_export")
        if getattr(app.tasks, "is_script_running", False):
            keys.add("script")
        if getattr(app.tasks, "is_sheet_running", False):
            keys.add("production_sheet")
        return keys

    def _relayout_cards(self, *, force: bool = False) -> None:
        width = max(self.width(), 400)
        columns = 3 if width >= 1100 else 2 if width >= 720 else 1
        if not force and columns == self._card_columns:
            return
        self._card_columns = columns
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self._cards_host)
        ordered = sorted(
            self._cards.items(),
            key=lambda item: (self._asset_stage.get(item[0], ""), item[0]),
        )
        for index, (_asset_id, card) in enumerate(ordered):
            card.setMinimumWidth(_CARD_MIN_WIDTH)
            row, col = divmod(index, columns)
            self._cards_grid.addWidget(card, row, col)
        for col in range(columns):
            self._cards_grid.setColumnStretch(col, 1)
