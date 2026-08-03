"""Reliability: QThread worker cleanup — no leaked threads."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from PySide6.QtCore import QThread

from app.tasks.creative_brief_worker import CreativeBriefWorker
from tests.reliability_support import ensure_qapp


def _wait_thread_finished(thread: QThread, *, timeout_s: float = 10.0) -> bool:
    """Wait for QThread finish while pumping Qt events (queued quit needs this)."""
    app = ensure_qapp()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if thread.isFinished():
            return True
        time.sleep(0.01)
    app.processEvents()
    return bool(thread.isFinished())


class _FakeBrief:
    summary = "ok"


class _FakeService:
    def __init__(self, *, delay_s: float = 0.15, fail: bool = False) -> None:
        self.delay_s = delay_s
        self.fail = fail
        self.cancel_calls = 0

    def cancel_analyze(self) -> None:
        self.cancel_calls += 1

    def analyze_script(self, script_text: str, output_path=None, progress=None):
        if progress:
            progress("working…")
        time.sleep(self.delay_s)
        if self.fail:
            raise RuntimeError("simulated failure")
        return _FakeBrief()


def _run_worker(service, script: str, out: Path) -> tuple[QThread, CreativeBriefWorker, list[str]]:
    """Start an unparented QThread with CreativeBriefWorker (production pattern)."""
    ensure_qapp()
    thread = QThread()  # intentionally unparented
    worker = CreativeBriefWorker(service, script, out)
    worker.moveToThread(thread)
    outcomes: list[str] = []

    worker.finished.connect(lambda _b: outcomes.append("finished"))
    worker.failed.connect(lambda _m: outcomes.append("failed"))
    worker.cancelled.connect(lambda: outcomes.append("cancelled"))
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    worker.cancelled.connect(thread.quit)
    # Do not call deleteLater here — tests assert lifecycle without Qt deferred
    # deletes that can abort the interpreter during unittest teardown on Windows.
    thread.start()
    return thread, worker, outcomes


class ThreadCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_qapp()

    def test_worker_thread_finishes_cleanly(self) -> None:
        service = _FakeService(delay_s=0.1)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "brief.json"
            thread, worker, outcomes = _run_worker(service, "script text", out)
            self.assertTrue(_wait_thread_finished(thread, timeout_s=10.0))
            self.assertIn("finished", outcomes)
            self.assertFalse(thread.isRunning())
            del worker
            del thread
            ensure_qapp().processEvents()

    def test_cancelled_worker_emits_cancelled(self) -> None:
        app = ensure_qapp()
        service = _FakeService(delay_s=0.25, fail=True)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "brief.json"
            thread, worker, outcomes = _run_worker(service, "script", out)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and not thread.isRunning():
                app.processEvents()
                time.sleep(0.01)
            worker.request_cancel()
            self.assertTrue(_wait_thread_finished(thread, timeout_s=10.0))
            self.assertIn("cancelled", outcomes)
            self.assertGreaterEqual(service.cancel_calls, 1)
            self.assertFalse(thread.isRunning())

    def test_sequential_workers_no_accumulation(self) -> None:
        service = _FakeService(delay_s=0.05)
        alive: list[QThread] = []

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "brief.json"
            for _ in range(5):
                thread, worker, outcomes = _run_worker(service, "x", out)
                alive.append(thread)
                self.assertTrue(_wait_thread_finished(thread, timeout_s=10.0))
                self.assertIn("finished", outcomes)
                self.assertFalse(thread.isRunning())
                del worker

        running = [t for t in alive if t.isRunning()]
        self.assertEqual(running, [], msg=f"Leaked running QThreads: {len(running)}")
        # All sequential workers finished — no accumulation of live runners.
        self.assertTrue(all(t.isFinished() for t in alive))


if __name__ == "__main__":
    unittest.main()
