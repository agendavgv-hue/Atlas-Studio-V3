"""Pipeline lifecycle states."""

from __future__ import annotations

from enum import Enum


class PipelineState(str, Enum):
    READY = "Ready"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
