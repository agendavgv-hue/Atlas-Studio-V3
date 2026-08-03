"""Tests for one-click GenerationQueue orchestration."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.pipelines.results import PipelineOutcome, PipelineResult
from app.tasks.generation_queue import PRODUCTION_STEPS, GenerationQueue, ProductionStep
from app.tasks.instagram_export import create_instagram_image, verify_youtube_export
from PySide6.QtCore import QObject, Signal


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _wait_until(predicate, *, timeout: float = 5.0) -> None:
    app = _ensure_app()
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for condition")


class _FakeTasks(QObject):
    script_progress = Signal(str)
    script_finished = Signal(object)
    script_running_changed = Signal(bool)
    sheet_progress = Signal(str)
    sheet_finished = Signal(object)
    sheet_running_changed = Signal(bool)
    image_progress = Signal(object)
    image_finished = Signal(object)
    image_running_changed = Signal(bool)
    voice_progress = Signal(object)
    voice_finished = Signal(object)
    voice_running_changed = Signal(bool)
    movie_progress = Signal(object)
    movie_finished = Signal(object)
    movie_running_changed = Signal(bool)
    thumbnail_progress = Signal(object)
    thumbnail_finished = Signal(object)
    thumbnail_running_changed = Signal(bool)
    shorts_progress = Signal(object)
    shorts_finished = Signal(object)
    shorts_running_changed = Signal(bool)
    instagram_progress = Signal(str)
    instagram_finished = Signal(object)
    instagram_running_changed = Signal(bool)
    export_progress = Signal(str)
    export_finished = Signal(object)
    export_running_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.busy = False
        self.cancelled = False
        self.started: list[str] = []
        self._fail_step: str | None = None

    @property
    def is_busy(self) -> bool:
        return self.busy

    def stop_current(self, *, status: str | None = None) -> None:
        self.cancelled = True

    def _run(self, kind: str, finished_signal, running_signal) -> bool:
        if self.busy:
            return False
        self.busy = True
        self.started.append(kind)
        running_signal.emit(True)
        if self._fail_step == kind:
            result = PipelineResult.failed(f"{kind} failed", errors=[f"{kind} failed"])
        elif self.cancelled:
            result = PipelineResult.cancelled()
        else:
            result = PipelineResult.success(f"{kind} ok")
        finished_signal.emit(result)
        self.busy = False
        running_signal.emit(False)
        return True

    def start_script(self, *args, **kwargs) -> bool:
        return self._run("script", self.script_finished, self.script_running_changed)

    def start_sheet(self, *args, **kwargs) -> bool:
        return self._run("sheet", self.sheet_finished, self.sheet_running_changed)

    def start_images(self, *args, **kwargs) -> bool:
        return self._run("images", self.image_finished, self.image_running_changed)

    def start_voice(self, *args, **kwargs) -> bool:
        return self._run("voice", self.voice_finished, self.voice_running_changed)

    def start_movie(self, *args, **kwargs) -> bool:
        return self._run("movie", self.movie_finished, self.movie_running_changed)

    def start_thumbnail(self, *args, **kwargs) -> bool:
        return self._run("thumbnail", self.thumbnail_finished, self.thumbnail_running_changed)

    def start_shorts(self, *args, **kwargs) -> bool:
        return self._run("shorts", self.shorts_finished, self.shorts_running_changed)

    def start_instagram(self, *args, **kwargs) -> bool:
        return self._run("instagram", self.instagram_finished, self.instagram_running_changed)

    def start_export(self, *args, **kwargs) -> bool:
        return self._run("export", self.export_finished, self.export_running_changed)


class _Ctx:
    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir


def test_production_steps_order() -> None:
    # TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
    assert [s.step for s in PRODUCTION_STEPS] == [
        ProductionStep.SCRIPT,
        ProductionStep.SHEET,
        ProductionStep.IMAGES,
        ProductionStep.VOICE,
        ProductionStep.MOVIE,
        ProductionStep.INSTAGRAM,
        ProductionStep.SHORT_1,
        ProductionStep.SHORT_2,
        ProductionStep.EXPORT,
    ]


def test_generation_queue_runs_all_steps(tmp_path: Path) -> None:
    _ensure_app()
    tasks = _FakeTasks()
    queue = GenerationQueue(tasks)  # type: ignore[arg-type]
    finished: list[PipelineResult] = []
    logs: list[str] = []
    queue.finished.connect(finished.append)
    queue.log_line.connect(logs.append)

    assert queue.start(
        engine=object(),  # type: ignore[arg-type]
        context=_Ctx(tmp_path),  # type: ignore[arg-type]
        channel_name="Ch",
        project_folder="P001",
    )

    _wait_until(lambda: not queue.is_running)
    assert len(finished) == 1
    assert finished[0].outcome == PipelineOutcome.SUCCESS
    assert tasks.started == [
        "script",
        "sheet",
        "images",
        "voice",
        "movie",
        "instagram",
        "shorts",
        "shorts",
        "export",
    ]
    joined = "\n".join(logs)
    assert "Starting Script..." in joined
    assert "Script Finished" in joined
    assert "Short 1 Finished" in joined
    assert "Short 2 Finished" in joined
    assert "Production Completed" in joined
    assert (tmp_path / "atlas.log").is_file()


def test_generation_queue_stops_on_fatal_error(tmp_path: Path) -> None:
    _ensure_app()
    tasks = _FakeTasks()
    tasks._fail_step = "voice"
    queue = GenerationQueue(tasks)  # type: ignore[arg-type]
    finished: list[PipelineResult] = []
    queue.finished.connect(finished.append)

    queue.start(
        engine=object(),  # type: ignore[arg-type]
        context=_Ctx(tmp_path),  # type: ignore[arg-type]
        channel_name="Ch",
        project_folder="P001",
    )
    _wait_until(lambda: not queue.is_running)
    assert finished[0].outcome == PipelineOutcome.FAILED
    assert "voice" in finished[0].message
    assert tasks.started == ["script", "sheet", "images", "voice"]


def test_instagram_and_export_helpers(tmp_path: Path) -> None:
    _ensure_app()
    thumb_dir = tmp_path / "thumbnail"
    thumb_dir.mkdir()
    source = thumb_dir / "thumbnail.png"
    source.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
    )

    result = create_instagram_image(tmp_path)
    assert result.ok
    assert (tmp_path / "insta" / "instagram.png").is_file()

    missing = verify_youtube_export(tmp_path)
    assert missing.outcome == PipelineOutcome.FAILED

    yt = tmp_path / "youtube_video"
    yt.mkdir(exist_ok=True)
    video = yt / "video.mp4"
    video.write_bytes(b"fake")
    ok = verify_youtube_export(tmp_path)
    assert ok.ok
