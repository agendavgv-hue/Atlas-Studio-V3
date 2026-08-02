"""Shared JSON helpers for Creative Director models."""

from __future__ import annotations

from dataclasses import asdict, fields
from typing import Any, TypeVar

T = TypeVar("T")


def to_dict(instance: Any) -> dict[str, Any]:
    return asdict(instance)


def from_dict(cls: type[T], data: dict[str, Any] | None) -> T:
    raw = dict(data or {})
    kwargs: dict[str, Any] = {}
    for item in fields(cls):  # type: ignore[arg-type]
        if item.name not in raw:
            continue
        value = raw[item.name]
        if value is None:
            continue
        if isinstance(value, list):
            kwargs[item.name] = list(value)
        elif isinstance(value, dict):
            kwargs[item.name] = dict(value)
        else:
            kwargs[item.name] = value
    return cls(**kwargs)  # type: ignore[misc]
