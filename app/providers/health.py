"""Structured provider health results for diagnostics and Settings UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthCheckItem:
    """One named step in a provider self-test."""

    key: str
    ok: bool
    message: str = ""


@dataclass(frozen=True)
class ProviderHealth:
    """Aggregate self-test result. Safe for Settings / diagnostics (does not raise)."""

    ok: bool
    provider_id: str
    message: str
    checks: tuple[HealthCheckItem, ...] = ()
    elapsed_ms: float = 0.0

    def check(self, key: str) -> HealthCheckItem | None:
        for item in self.checks:
            if item.key == key:
                return item
        return None
