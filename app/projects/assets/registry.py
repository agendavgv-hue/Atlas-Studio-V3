"""AssetRegistry — project production inventory (status source of truth)."""

from __future__ import annotations

import re
from pathlib import Path

from app.artifacts import ArtifactKind, ArtifactResolver
from app.artifacts.rules import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from app.pipelines.results import PipelineOutcome, PipelineResult
from app.projects.assets.catalog import (
    CORE_ASSET_SPECS,
    PIPELINE_TO_ASSET,
    image_asset_id,
    make_core_asset,
    make_image_asset,
)
from app.projects.assets.models import (
    AssetCatalog,
    AssetStatus,
    AssetType,
    ProjectAsset,
)
from app.projects.assets.store import AssetStore
from app.projects.production_stages import (
    StageSnapshot,
    StageState,
    VISIBLE_STAGES,
    WorkflowSnapshot,
    resolve_primary_action,
)

_IMAGE_NAME = re.compile(r"image[_\s-]?(\d+)", re.IGNORECASE)
_SHORT_NAME = re.compile(r"short[_\s-]?(\d+)", re.IGNORECASE)


class AssetRegistry:
    """Load / seed / update production assets for one project folder."""

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir.expanduser().resolve()
        self._store = AssetStore(self._project_dir)

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    def load(self) -> AssetCatalog:
        catalog = self._store.load()
        if not catalog.assets:
            catalog = self.ensure_inventory(reconcile_disk=True)
        return catalog

    def save(self, catalog: AssetCatalog) -> None:
        self._store.save(catalog)

    def ensure_inventory(self, *, reconcile_disk: bool = True) -> AssetCatalog:
        """Guarantee core assets exist; optionally sync Ready from disk once."""
        catalog = self._store.load()
        changed = False
        for spec in CORE_ASSET_SPECS:
            if catalog.get(spec.id) is None:
                catalog.upsert(make_core_asset(spec))
                changed = True
        if reconcile_disk:
            if self._reconcile_from_disk(catalog):
                changed = True
        if changed or not self._store.path.is_file():
            self._store.save(catalog)
        return catalog

    def set_status(
        self,
        asset_id: str,
        status: AssetStatus,
        *,
        location: str | None = None,
        generator: str = "",
        message: str = "",
    ) -> ProjectAsset | None:
        catalog = self.ensure_inventory(reconcile_disk=False)
        asset = catalog.get(asset_id)
        if asset is None:
            return None
        if status is AssetStatus.READY and location:
            asset.mark_ready(location, generator=generator or asset.generator)
        elif status is AssetStatus.FAILED:
            asset.mark_failed(message=message)
        elif status is AssetStatus.IN_PROGRESS:
            asset.mark_in_progress(generator=generator or asset.generator)
        else:
            asset.touch(status=status)
            if location:
                asset.location = location
        catalog.upsert(asset)
        self._store.save(catalog)
        return asset

    def ensure_image_slots(self, count: int | None = None) -> AssetCatalog:
        """Create Image 01..N placeholders (from sheet scene count when known)."""
        from app.pipelines.sheet_format import REQUIRED_SCENE_COUNT

        catalog = self.ensure_inventory(reconcile_disk=False)
        target = count if count is not None and count > 0 else REQUIRED_SCENE_COUNT
        changed = self._ensure_image_slots(catalog, target)
        if changed:
            self._store.save(catalog)
        return catalog

    def mark_pipeline_started(self, pipeline_id: str) -> None:
        catalog = self.ensure_inventory(reconcile_disk=False)
        if pipeline_id == "images":
            self._ensure_image_slots(catalog, self._scene_count_hint(catalog))
        asset_ids = self._asset_ids_for_pipeline(pipeline_id, catalog)
        for asset_id in asset_ids:
            asset = catalog.get(asset_id)
            if asset is None:
                continue
            asset.mark_in_progress(generator=pipeline_id)
            catalog.upsert(asset)
        self._store.save(catalog)

    def record_pipeline_result(
        self,
        pipeline_id: str,
        result: PipelineResult,
    ) -> AssetCatalog:
        """Update assets after a pipeline finishes (success or failure)."""
        catalog = self.ensure_inventory(reconcile_disk=False)
        generator = pipeline_id

        if result.outcome == PipelineOutcome.CANCELLED:
            for asset_id in self._asset_ids_for_pipeline(pipeline_id, catalog):
                asset = catalog.get(asset_id)
                if asset and asset.status is AssetStatus.IN_PROGRESS:
                    asset.touch(status=AssetStatus.NOT_STARTED)
                    catalog.upsert(asset)
            self._store.save(catalog)
            return catalog

        if not result.ok:
            for asset_id in self._asset_ids_for_pipeline(pipeline_id, catalog):
                asset = catalog.get(asset_id)
                if asset is None:
                    continue
                asset.mark_failed(message=result.message)
                catalog.upsert(asset)
            self._store.save(catalog)
            return catalog

        artifacts = [
            self._normalize_artifact_path(a) for a in result.artifacts if a
        ]

        if pipeline_id == "images":
            self._ensure_image_slots(catalog, self._scene_count_hint(catalog))
            self._record_images(catalog, artifacts, generator=generator)
        elif pipeline_id == "shorts":
            self._record_shorts(catalog, artifacts, generator=generator)
        else:
            asset_id = PIPELINE_TO_ASSET.get(pipeline_id)
            if asset_id:
                asset = catalog.get(asset_id)
                if asset is not None:
                    location = artifacts[0] if artifacts else asset.location
                    asset.mark_ready(location, generator=generator)
                    catalog.upsert(asset)
            if pipeline_id == "production_sheet":
                self._ensure_image_slots(catalog, self._scene_count_hint(catalog))
            # Export verification also marks movie ready if present.
            if pipeline_id in {"export", "youtube_export"} and artifacts:
                movie = catalog.get("movie")
                if movie is not None and not movie.status.is_complete:
                    movie.mark_ready(artifacts[0], generator=generator)
                    catalog.upsert(movie)

        self._store.save(catalog)
        return catalog

    def workflow_snapshot(
        self,
        *,
        running_keys: frozenset[str] | set[str] | None = None,
        failed_keys: frozenset[str] | set[str] | None = None,
    ) -> WorkflowSnapshot:
        """Build guided workflow snapshot from tracked assets (not folder scans)."""
        catalog = self.load()
        running = set(running_keys or ())
        failed_overlay = set(failed_keys or ())

        stages: list[StageSnapshot] = []
        for spec in VISIBLE_STAGES:
            assets = catalog.by_stage(spec.key)
            if not assets and spec.key == "images":
                # Images may be empty until sheet/generation — treat as not started.
                state = StageState.NOT_STARTED
                detail = "Not started"
                count_done = 0
            else:
                state, detail, count_done = self._stage_from_assets(
                    assets, spec.key, running, failed_overlay
                )
            stages.append(
                StageSnapshot(
                    key=spec.key,
                    label=spec.label,
                    state=state,
                    detail=detail,
                    count_done=count_done,
                    count_total=len(assets) if spec.key == "images" and assets else None,
                )
            )

        done = sum(1 for s in stages if s.state is StageState.COMPLETED)
        total = max(1, len(stages))
        percent = int(round(100.0 * done / total))
        next_key = next(
            (s.key for s in stages if s.state is not StageState.COMPLETED), None
        )
        primary_action, primary_key = resolve_primary_action(tuple(stages), next_key)
        return WorkflowSnapshot(
            stages=tuple(stages),
            percent=percent,
            next_key=next_key,
            primary_action=primary_action,
            primary_stage_key=primary_key,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _stage_from_assets(
        self,
        assets: list[ProjectAsset],
        stage_key: str,
        running: set[str],
        failed_overlay: set[str],
    ) -> tuple[StageState, str, int]:
        if stage_key in running:
            return StageState.IN_PROGRESS, "In progress…", 0
        if not assets:
            return StageState.NOT_STARTED, "Not started", 0

        ready = [a for a in assets if a.status.is_complete]
        failed = [a for a in assets if a.status is AssetStatus.FAILED]
        in_prog = [a for a in assets if a.status is AssetStatus.IN_PROGRESS]

        if in_prog:
            return StageState.IN_PROGRESS, "In progress…", len(ready)
        if stage_key in failed_overlay or (failed and not ready):
            return StageState.FAILED, "Failed — retry", len(ready)
        if stage_key == "images":
            if ready and len(ready) == len(assets):
                return (
                    StageState.COMPLETED,
                    f"{len(ready)} image{'s' if len(ready) != 1 else ''}",
                    len(ready),
                )
            if ready:
                return (
                    StageState.IN_PROGRESS,
                    f"{len(ready)} / {len(assets)} images",
                    len(ready),
                )
            return StageState.NOT_STARTED, "Not started", 0
        if stage_key == "shorts":
            if len(ready) >= 1:
                return StageState.COMPLETED, f"{len(ready)} short(s)", len(ready)
            return StageState.NOT_STARTED, "Not started", 0
        # Single-asset stages
        primary = assets[0]
        if primary.status.is_complete:
            return StageState.COMPLETED, "Ready", 1
        if primary.status is AssetStatus.FAILED:
            return StageState.FAILED, "Failed — retry", 0
        return StageState.NOT_STARTED, primary.status.label, 0

    def _asset_ids_for_pipeline(
        self, pipeline_id: str, catalog: AssetCatalog
    ) -> list[str]:
        if pipeline_id == "images":
            return [a.id for a in catalog.assets if a.type is AssetType.IMAGE]
        if pipeline_id == "shorts":
            return ["short_1", "short_2"]
        asset_id = PIPELINE_TO_ASSET.get(pipeline_id)
        return [asset_id] if asset_id else []

    def _ensure_image_slots(self, catalog: AssetCatalog, count: int) -> bool:
        changed = False
        for index in range(1, max(0, count) + 1):
            asset_id = image_asset_id(index)
            if catalog.get(asset_id) is None:
                catalog.upsert(make_image_asset(index))
                changed = True
        return changed

    def _scene_count_hint(self, catalog: AssetCatalog) -> int:
        from app.pipelines.sheet_format import REQUIRED_SCENE_COUNT
        from app.pipelines.sheet_prompts import iter_image_blocks

        sheet = catalog.get("production_sheet")
        if sheet and sheet.location:
            path = self._project_dir / sheet.location
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    indexes = {block.index for block in iter_image_blocks(text)}
                    if indexes:
                        return max(REQUIRED_SCENE_COUNT, max(indexes))
                except OSError:
                    pass
        return REQUIRED_SCENE_COUNT

    def _normalize_artifact_path(self, raw: str | Path) -> str:
        path = Path(raw)
        try:
            if path.is_absolute():
                return str(path.resolve().relative_to(self._project_dir)).replace(
                    "\\", "/"
                )
        except ValueError:
            pass
        return str(raw).replace("\\", "/")

    def _record_images(
        self, catalog: AssetCatalog, artifacts: list[str], *, generator: str
    ) -> None:
        if not artifacts:
            return
        for path in artifacts:
            name = Path(path).name
            match = _IMAGE_NAME.search(name)
            index = int(match.group(1)) if match else None
            if index is None:
                existing = [a for a in catalog.assets if a.type is AssetType.IMAGE]
                index = len(existing) + 1
            asset = catalog.get(image_asset_id(index)) or make_image_asset(
                index, location=path
            )
            asset.mark_ready(path, generator=generator)
            catalog.upsert(asset)

    def _record_shorts(
        self, catalog: AssetCatalog, artifacts: list[str], *, generator: str
    ) -> None:
        videos = [a for a in artifacts if a.lower().endswith((".mp4", ".mov", ".webm"))]
        if not videos:
            videos = artifacts
        for index, path in enumerate(videos[:2], start=1):
            asset_id = f"short_{index}"
            asset = catalog.get(asset_id)
            if asset is None:
                continue
            asset.mark_ready(path, generator=generator)
            catalog.upsert(asset)

    def _reconcile_from_disk(self, catalog: AssetCatalog) -> bool:
        """Seed Ready status from existing files (migration / first open)."""
        changed = False
        resolver = ArtifactResolver(self._project_dir)

        mapping = [
            ("script", ArtifactKind.SCRIPT),
            ("production_sheet", ArtifactKind.PRODUCTION_SHEET),
            ("voice_over", ArtifactKind.VOICE),
            ("movie", ArtifactKind.YOUTUBE_EXPORT),
            ("export_package", ArtifactKind.YOUTUBE_EXPORT),
            ("thumbnail", ArtifactKind.THUMBNAIL),
        ]
        for asset_id, kind in mapping:
            asset = catalog.get(asset_id)
            if asset is None or asset.status.is_complete:
                continue
            found = resolver.find(kind)
            if found is None:
                # Movie may exist as working mp4 only
                if asset_id == "movie":
                    found = self._first_media(self._project_dir / "mp4", VIDEO_EXTENSIONS)
                else:
                    continue
            if found is None:
                continue
            rel = self._rel(found)
            asset.mark_ready(rel, generator=asset.generator or "import")
            catalog.upsert(asset)
            changed = True

        # Images
        for folder_name in ("images", "image"):
            folder = self._project_dir / folder_name
            if not folder.is_dir():
                continue
            for path in sorted(folder.iterdir()):
                if not path.is_file() or path.suffix.casefold() not in IMAGE_EXTENSIONS:
                    continue
                match = _IMAGE_NAME.search(path.name)
                index = int(match.group(1)) if match else None
                if index is None:
                    continue
                asset = catalog.get(image_asset_id(index)) or make_image_asset(index)
                if not asset.status.is_complete:
                    asset.mark_ready(self._rel(path), generator="import")
                    catalog.upsert(asset)
                    changed = True

        # Shorts
        short_dir = self._project_dir / "short"
        if short_dir.is_dir():
            videos = sorted(
                p
                for p in short_dir.iterdir()
                if p.is_file() and p.suffix.casefold() in VIDEO_EXTENSIONS
            )
            for index, path in enumerate(videos[:2], start=1):
                asset = catalog.get(f"short_{index}")
                if asset and not asset.status.is_complete:
                    asset.mark_ready(self._rel(path), generator="import")
                    catalog.upsert(asset)
                    changed = True

        return changed

    def _rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self._project_dir)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    @staticmethod
    def _first_media(folder: Path, extensions: frozenset[str] | set[str]) -> Path | None:
        if not folder.is_dir():
            return None
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix.casefold() in extensions:
                return path
        return None
