"""Production workflow stages — guided YouTube production (no UI coupling)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class StageState(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def label(self) -> str:
        return {
            StageState.NOT_STARTED: "Not started",
            StageState.IN_PROGRESS: "In progress",
            StageState.COMPLETED: "Completed",
            StageState.FAILED: "Failed",
        }[self]

    @property
    def icon_state(self) -> str:
        """Map to status_icon_pixmap keys."""
        return {
            StageState.NOT_STARTED: "not_started",
            StageState.IN_PROGRESS: "running",
            StageState.COMPLETED: "complete",
            StageState.FAILED: "failed",
        }[self]


@dataclass(frozen=True)
class ProductionStageDef:
    """Declarative stage — add future stages without redesigning the hub."""

    key: str
    label: str
    primary_label: str  # Generate Script / Generate Movie / …
    supports_open: bool = True
    supports_regenerate: bool = True
    supports_preview: bool = False
    open_label: str = "Open"
    # Optional future stages stay registered but hidden from V3 hub.
    visible: bool = True


# Guided production order (V3). Thumbnail reserved for V3.1.
PRODUCTION_STAGE_DEFS: tuple[ProductionStageDef, ...] = (
    ProductionStageDef("script", "Script", "Generate Script", open_label="Open Script"),
    ProductionStageDef(
        "production_sheet",
        "Production Sheet",
        "Generate Sheet",
        open_label="Open Sheet",
    ),
    ProductionStageDef(
        "voice",
        "Voice-over",
        "Generate Voice-over",
        supports_preview=True,
        open_label="Open Folder",
    ),
    ProductionStageDef(
        "images",
        "Images",
        "Generate Images",
        open_label="Open Folder",
    ),
    ProductionStageDef(
        "movie",
        "Movie",
        "Generate Movie",
        supports_preview=True,
        open_label="Open Folder",
    ),
    ProductionStageDef(
        "shorts",
        "Shorts",
        "Generate Shorts",
        supports_preview=True,
        open_label="Open Folder",
    ),
    ProductionStageDef(
        "youtube_export",
        "Export",
        "Export Package",
        supports_regenerate=False,
        open_label="Open Folder",
    ),
    # TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
    ProductionStageDef(
        "thumbnail",
        "Thumbnail",
        "Generate Thumbnail",
        visible=False,
    ),
)

VISIBLE_STAGES: tuple[ProductionStageDef, ...] = tuple(
    s for s in PRODUCTION_STAGE_DEFS if s.visible
)


@dataclass(frozen=True)
class StageSnapshot:
    key: str
    label: str
    state: StageState
    detail: str = ""
    count_done: int = 0
    count_total: int | None = None

    @property
    def complete(self) -> bool:
        return self.state is StageState.COMPLETED


@dataclass(frozen=True)
class WorkflowSnapshot:
    stages: tuple[StageSnapshot, ...]
    percent: int
    next_key: str | None
    primary_action: str
    primary_stage_key: str | None

    def stage(self, key: str) -> StageSnapshot | None:
        for item in self.stages:
            if item.key == key:
                return item
        return None


def scan_workflow(
    project_dir: Path,
    *,
    running_keys: frozenset[str] | set[str] | None = None,
    failed_keys: frozenset[str] | set[str] | None = None,
) -> WorkflowSnapshot:
    """Build workflow status from tracked assets (assets.json).

    Disk reconcile runs once when the inventory is first created. After that,
    pipeline results update asset status — no arbitrary folder scanning.
    """
    from app.projects.assets.registry import AssetRegistry

    return AssetRegistry(project_dir).workflow_snapshot(
        running_keys=running_keys,
        failed_keys=failed_keys,
    )


def resolve_primary_action(
    stages: tuple[StageSnapshot, ...],
    next_key: str | None,
) -> tuple[str, str | None]:
    """Single guided CTA label + stage key."""
    if not stages:
        return "Generate Everything", None
    if all(s.state is StageState.COMPLETED for s in stages):
        return "Production Complete", None
    if all(s.state is StageState.NOT_STARTED for s in stages):
        return "Generate Everything", None
    if next_key:
        for spec in VISIBLE_STAGES:
            if spec.key == next_key:
                if any(s.key == next_key and s.state is StageState.FAILED for s in stages):
                    return f"Retry {spec.label}", next_key
                if any(
                    s.key == next_key and s.state is StageState.IN_PROGRESS for s in stages
                ):
                    return "Continue Production", next_key
                return spec.primary_label, next_key
    return "Continue Production", next_key


def stage_def(key: str) -> ProductionStageDef | None:
    for spec in PRODUCTION_STAGE_DEFS:
        if spec.key == key:
            return spec
    return None


def progress_summary_line(snapshot: WorkflowSnapshot) -> str:
    """Compact line for Projects list / Dashboard."""
    parts: list[str] = []
    for s in snapshot.stages:
        mark = "✓" if s.state is StageState.COMPLETED else "○"
        parts.append(f"{mark} {s.label}")
    return f"{snapshot.percent}%  ·  " + "  ".join(parts)
