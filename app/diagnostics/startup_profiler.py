"""Real end-to-end startup profiler for Atlas Studio.

Measures wall-clock stages from process entry until the main window is
fully interactive. Stdlib-only so it can be imported before heavy app code.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


_INSTALL_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LOG_DIR = _INSTALL_ROOT / "logs"


@dataclass
class StageRecord:
    """One timed startup stage."""

    name: str
    status: str  # completed | skipped | failed | milestone
    duration_ms: float
    start_ms: float
    end_ms: float
    note: str = ""


@dataclass
class StartupProfile:
    """Complete profile for one process launch."""

    start_timestamp: str
    total_startup_ms: float
    stages: list[StageRecord] = field(default_factory=list)
    longest_operations: list[dict[str, object]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    log_dir: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "start_timestamp": self.start_timestamp,
            "total_startup_ms": round(self.total_startup_ms, 3),
            "stages": [asdict(stage) for stage in self.stages],
            "longest_operations": self.longest_operations,
            "recommendations": self.recommendations,
            "notes": self.notes,
            "log_dir": self.log_dir,
        }


class StartupProfiler:
    """Singleton profiler bound to one Atlas process launch."""

    _instance: StartupProfiler | None = None

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._wall_start = datetime.now(timezone.utc).isoformat()
        self._open: dict[str, float] = {}
        self._stages: list[StageRecord] = []
        self._order: list[str] = []
        self._by_name: dict[str, StageRecord] = {}
        self._finalized = False
        self._profile: StartupProfile | None = None
        self._notes: list[str] = []

    @classmethod
    def instance(cls) -> StartupProfiler:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> StartupProfiler:
        cls._instance = cls()
        return cls._instance

    def bind_process_start(self, perf_counter: float, wall_iso: str) -> None:
        """Anchor timings to the earliest entry-script timestamp."""
        if self._stages or self._open:
            return
        self._t0 = perf_counter
        self._wall_start = wall_iso

    @property
    def start_timestamp(self) -> str:
        return self._wall_start

    @property
    def profile(self) -> StartupProfile | None:
        return self._profile

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0

    def add_note(self, note: str) -> None:
        text = (note or "").strip()
        if text and text not in self._notes:
            self._notes.append(text)

    def begin(self, name: str, *, at_perf: float | None = None) -> None:
        key = name.strip()
        if not key or self._finalized:
            return
        self._open[key] = at_perf if at_perf is not None else time.perf_counter()

    def end(
        self,
        name: str,
        *,
        status: str = "completed",
        note: str = "",
    ) -> StageRecord | None:
        key = name.strip()
        if not key or self._finalized:
            return None
        started = self._open.pop(key, None)
        now = time.perf_counter()
        if started is None:
            started = now
        return self._record(
            key,
            status=status,
            start_perf=started,
            end_perf=now,
            note=note,
        )

    def mark(
        self,
        name: str,
        *,
        status: str = "milestone",
        note: str = "",
        at_perf: float | None = None,
    ) -> StageRecord | None:
        """Record a zero-width milestone at the current (or given) elapsed time."""
        now = at_perf if at_perf is not None else time.perf_counter()
        return self._record(
            name.strip(),
            status=status,
            start_perf=now,
            end_perf=now,
            note=note,
        )

    def skip(self, name: str, reason: str) -> StageRecord | None:
        now = time.perf_counter()
        return self._record(
            name.strip(),
            status="skipped",
            start_perf=now,
            end_perf=now,
            note=reason,
        )

    @contextmanager
    def stage(self, name: str, *, note: str = "") -> Iterator[None]:
        self.begin(name)
        try:
            yield
        except Exception as exc:  # noqa: BLE001
            self.end(name, status="failed", note=f"{note}; {exc}".strip("; "))
            raise
        else:
            self.end(name, status="completed", note=note)

    def _record(
        self,
        name: str,
        *,
        status: str,
        start_perf: float,
        end_perf: float,
        note: str,
    ) -> StageRecord:
        start_ms = (start_perf - self._t0) * 1000.0
        end_ms = (end_perf - self._t0) * 1000.0
        duration_ms = max(0.0, end_ms - start_ms)
        record = StageRecord(
            name=name,
            status=status,
            duration_ms=round(duration_ms, 3),
            start_ms=round(start_ms, 3),
            end_ms=round(end_ms, 3),
            note=note or "",
        )
        if name in self._by_name:
            # Replace prior record for the same name (re-measure).
            old = self._by_name[name]
            for index, existing in enumerate(self._stages):
                if existing is old:
                    self._stages[index] = record
                    break
        else:
            self._stages.append(record)
            self._order.append(name)
        self._by_name[name] = record
        return record

    def finalize(
        self,
        *,
        log_dir: Path | None = None,
        write_files: bool = True,
    ) -> StartupProfile:
        """Close open stages, compute totals, optionally write logs."""
        if self._finalized and self._profile is not None:
            return self._profile

        # Close any forgotten open stages.
        for name in list(self._open):
            self.end(name, status="completed", note="auto-closed at finalize")

        total_ms = self.elapsed_ms()
        completed = [
            stage
            for stage in self._stages
            if stage.status == "completed" and stage.duration_ms > 0
        ]
        longest = sorted(completed, key=lambda s: s.duration_ms, reverse=True)[:8]
        longest_ops = [
            {
                "name": stage.name,
                "duration_ms": stage.duration_ms,
                "note": stage.note,
            }
            for stage in longest
        ]
        recommendations = _build_recommendations(self._stages, total_ms)
        out_dir = (log_dir or _DEFAULT_LOG_DIR).resolve()
        profile = StartupProfile(
            start_timestamp=self._wall_start,
            total_startup_ms=round(total_ms, 3),
            stages=list(self._stages),
            longest_operations=longest_ops,
            recommendations=recommendations,
            notes=list(self._notes),
            log_dir=str(out_dir),
        )
        self._profile = profile
        self._finalized = True
        if write_files:
            write_startup_profile(profile, out_dir)
        return profile


def write_startup_profile(profile: StartupProfile, log_dir: Path) -> tuple[Path, Path]:
    """Write JSON + Markdown reports. Returns (json_path, md_path)."""
    log_dir.mkdir(parents=True, exist_ok=True)
    json_path = log_dir / "startup_profile.json"
    md_path = log_dir / "startup_profile.md"
    json_path.write_text(
        json.dumps(profile.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(profile), encoding="utf-8")
    return json_path, md_path


def load_startup_profile(log_dir: Path | None = None) -> dict[str, object] | None:
    path = (log_dir or _DEFAULT_LOG_DIR) / "startup_profile.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def default_log_dir() -> Path:
    return _DEFAULT_LOG_DIR


def _build_recommendations(stages: list[StageRecord], total_ms: float) -> list[str]:
    tips: list[str] = []
    by_name = {stage.name: stage for stage in stages}

    splash = by_name.get("splash_minimum_wait")
    if splash and splash.duration_ms >= 500:
        tips.append(
            f"Splash minimum wait accounts for {splash.duration_ms:.0f} ms of "
            "perceived startup (branding floor, not bootstrap work)."
        )

    imports = by_name.get("python_module_imports")
    if imports and imports.duration_ms >= 400:
        tips.append(
            "Python module imports dominate cold start; this includes PySide6 "
            "and application packages before QApplication exists."
        )

    theme = by_name.get("theme_loading")
    if theme and theme.duration_ms >= 100:
        tips.append("Theme/stylesheet application is measurable on the UI thread during QApplication init.")

    window = by_name.get("main_window_construct")
    if window and window.duration_ms >= 200:
        tips.append("Main window shell + sidebar construction is a notable chunk of interactive readiness.")

    dashboard = by_name.get("dashboard_creation")
    if dashboard and dashboard.duration_ms >= 50:
        tips.append("Dashboard creation runs before first show; keep landing page light.")

    skipped = [s for s in stages if s.status == "skipped"]
    if skipped:
        tips.append(
            f"{len(skipped)} stages were skipped at startup (deferred subsystems). "
            "They do not contribute to time-to-interactive."
        )

    if total_ms >= 3000:
        tips.append(
            "Total time-to-interactive includes splash branding wait. Compare "
            "`bootstrap_*` / construct stages when judging code cost vs UX floor."
        )
    elif not tips:
        tips.append("No single stage stands out; re-check after cold OS cache flush for worst-case numbers.")

    return tips


def _render_markdown(profile: StartupProfile) -> str:
    lines = [
        "# Atlas Studio Startup Profile",
        "",
        f"**Start timestamp:** {profile.start_timestamp}",
        f"**Total startup (entry -> fully interactive):** {profile.total_startup_ms:.1f} ms",
        "",
        "## Stages",
        "",
        "| Stage | Status | Duration (ms) | Start (ms) | End (ms) | Note |",
        "|-------|--------|---------------|------------|----------|------|",
    ]
    for stage in profile.stages:
        note = stage.note.replace("|", "\\|")
        lines.append(
            f"| `{stage.name}` | {stage.status} | {stage.duration_ms:.1f} | "
            f"{stage.start_ms:.1f} | {stage.end_ms:.1f} | {note} |"
        )

    lines.extend(["", "## Longest operations", ""])
    if not profile.longest_operations:
        lines.append("_None (no completed stages with duration > 0)._")
    else:
        for item in profile.longest_operations:
            lines.append(
                f"- **{item['name']}**: {float(item['duration_ms']):.1f} ms"
                + (f" - {item['note']}" if item.get("note") else "")
            )

    lines.extend(["", "## Recommendations", ""])
    for tip in profile.recommendations:
        lines.append(f"- {tip}")

    if profile.notes:
        lines.extend(["", "## Notes", ""])
        for note in profile.notes:
            lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## Methodology",
            "",
            "- Timings use `time.perf_counter()` anchored at the first line of `main.py`.",
            "- **Total startup** is process entry -> `fully_interactive` (main window shown, "
            "event queue drained once).",
            "- Skipped stages are subsystems not constructed during normal startup.",
            "- Splash minimum wait is included because it is part of real user experience.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"
