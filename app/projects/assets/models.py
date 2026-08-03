"""Production asset models — tracked items inside a project."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AssetStatus(str, Enum):
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    FAILED = "failed"
    APPROVED = "approved"  # future

    @property
    def label(self) -> str:
        return {
            AssetStatus.NOT_STARTED: "Not started",
            AssetStatus.QUEUED: "Queued",
            AssetStatus.IN_PROGRESS: "In progress",
            AssetStatus.READY: "Ready",
            AssetStatus.FAILED: "Failed",
            AssetStatus.APPROVED: "Approved",
        }[self]

    @property
    def icon_state(self) -> str:
        return {
            AssetStatus.NOT_STARTED: "not_started",
            AssetStatus.QUEUED: "running",
            AssetStatus.IN_PROGRESS: "running",
            AssetStatus.READY: "complete",
            AssetStatus.FAILED: "failed",
            AssetStatus.APPROVED: "complete",
        }[self]

    @property
    def is_complete(self) -> bool:
        return self in {AssetStatus.READY, AssetStatus.APPROVED}


class AssetType(str, Enum):
    SCRIPT = "script"
    PRODUCTION_SHEET = "production_sheet"
    VOICE = "voice"
    IMAGE = "image"
    THUMBNAIL = "thumbnail"
    MOVIE = "movie"
    SHORT = "short"
    EXPORT = "export"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class ProjectAsset:
    """One tracked production asset (script, image_03, movie, …)."""

    id: str
    type: AssetType
    label: str
    status: AssetStatus = AssetStatus.NOT_STARTED
    location: str = ""  # project-relative path
    generator: str = ""
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    stage_key: str = ""  # maps to production stage / primary CTA
    sort_index: int = 0
    meta: dict[str, Any] = field(default_factory=dict)
    visible: bool = True

    def touch(self, *, status: AssetStatus | None = None) -> None:
        now = _utc_now()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now
        if status is not None:
            self.status = status

    def mark_ready(self, location: str, *, generator: str = "") -> None:
        if self.status.is_complete:
            self.version += 1
        self.location = location
        if generator:
            self.generator = generator
        self.touch(status=AssetStatus.READY)

    def mark_failed(self, *, message: str = "") -> None:
        if message:
            self.meta["last_error"] = message
        self.touch(status=AssetStatus.FAILED)

    def mark_in_progress(self, *, generator: str = "") -> None:
        if generator:
            self.generator = generator
        self.touch(status=AssetStatus.IN_PROGRESS)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectAsset:
        raw = dict(data or {})
        try:
            asset_type = AssetType(str(raw.get("type") or "script"))
        except ValueError:
            asset_type = AssetType.SCRIPT
        try:
            status = AssetStatus(str(raw.get("status") or "not_started"))
        except ValueError:
            status = AssetStatus.NOT_STARTED
        return cls(
            id=str(raw.get("id") or ""),
            type=asset_type,
            label=str(raw.get("label") or raw.get("id") or ""),
            status=status,
            location=str(raw.get("location") or ""),
            generator=str(raw.get("generator") or ""),
            version=int(raw.get("version") or 1),
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
            stage_key=str(raw.get("stage_key") or ""),
            sort_index=int(raw.get("sort_index") or 0),
            meta=dict(raw.get("meta") or {}),
            visible=bool(raw.get("visible", True)),
        )


@dataclass
class AssetCatalog:
    """Full project asset inventory persisted as assets.json."""

    schema_version: int = 1
    assets: list[ProjectAsset] = field(default_factory=list)

    def get(self, asset_id: str) -> ProjectAsset | None:
        for asset in self.assets:
            if asset.id == asset_id:
                return asset
        return None

    def upsert(self, asset: ProjectAsset) -> ProjectAsset:
        for index, existing in enumerate(self.assets):
            if existing.id == asset.id:
                self.assets[index] = asset
                return asset
        self.assets.append(asset)
        self.assets.sort(key=lambda a: (a.sort_index, a.id))
        return asset

    def by_stage(self, stage_key: str) -> list[ProjectAsset]:
        return [a for a in self.assets if a.stage_key == stage_key and a.visible]

    def visible_assets(self) -> list[ProjectAsset]:
        return [a for a in self.assets if a.visible]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assets": [a.to_dict() for a in self.assets],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AssetCatalog:
        raw = dict(data or {})
        assets = [
            ProjectAsset.from_dict(item)
            for item in (raw.get("assets") or [])
            if isinstance(item, dict)
        ]
        assets.sort(key=lambda a: (a.sort_index, a.id))
        return cls(
            schema_version=int(raw.get("schema_version") or 1),
            assets=assets,
        )
