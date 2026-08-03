"""Tests for asset-centric production inventory."""

from __future__ import annotations

from pathlib import Path

from app.pipelines.results import PipelineResult
from app.pipelines.sheet_format import REQUIRED_SCENE_COUNT
from app.projects.assets.models import AssetStatus
from app.projects.assets.registry import AssetRegistry
from app.projects.production_stages import StageState, scan_workflow


def test_ensure_inventory_creates_core_assets(tmp_path: Path) -> None:
    catalog = AssetRegistry(tmp_path).ensure_inventory(reconcile_disk=False)
    ids = {a.id for a in catalog.assets}
    assert "script" in ids
    assert "production_sheet" in ids
    assert "voice_over" in ids
    assert "movie" in ids
    assert "short_1" in ids
    assert "short_2" in ids
    assert "export_package" in ids
    assert "thumbnail" in ids
    thumb = catalog.get("thumbnail")
    assert thumb is not None
    assert thumb.visible is False
    assert (tmp_path / "assets.json").is_file()


def test_disk_reconcile_once_then_pipeline_owns_status(tmp_path: Path) -> None:
    script_dir = tmp_path / "script"
    script_dir.mkdir()
    (script_dir / "script.txt").write_text("Narration line.", encoding="utf-8")

    registry = AssetRegistry(tmp_path)
    catalog = registry.load()
    script = catalog.get("script")
    assert script is not None
    assert script.status is AssetStatus.READY

    # Manual status change survives — no re-scan on load when inventory exists.
    registry.set_status("script", AssetStatus.NOT_STARTED)
    again = registry.load()
    assert again.get("script") is not None
    assert again.get("script").status is AssetStatus.NOT_STARTED


def test_record_pipeline_result_marks_ready(tmp_path: Path) -> None:
    registry = AssetRegistry(tmp_path)
    registry.ensure_inventory(reconcile_disk=False)
    result = PipelineResult.success(
        "ok",
        artifacts=[str(tmp_path / "script" / "script.txt")],
    )
    catalog = registry.record_pipeline_result("script", result)
    asset = catalog.get("script")
    assert asset is not None
    assert asset.status is AssetStatus.READY
    assert asset.location.endswith("script/script.txt")
    assert asset.generator == "script"
    assert asset.version >= 1


def test_production_sheet_creates_image_slots(tmp_path: Path) -> None:
    registry = AssetRegistry(tmp_path)
    registry.ensure_inventory(reconcile_disk=False)
    sheet_dir = tmp_path / "script"
    sheet_dir.mkdir()
    blocks = "\n".join(
        f"IMAGE {i:02d}\nPrompt: scene {i}\n" for i in range(1, REQUIRED_SCENE_COUNT + 1)
    )
    (sheet_dir / "production_sheet.txt").write_text(blocks, encoding="utf-8")

    result = PipelineResult.success(
        "ok",
        artifacts=["script/production_sheet.txt"],
    )
    catalog = registry.record_pipeline_result("production_sheet", result)
    images = [a for a in catalog.assets if a.id.startswith("image_")]
    assert len(images) == REQUIRED_SCENE_COUNT
    assert catalog.get("image_01") is not None
    assert catalog.get("image_01").status is AssetStatus.NOT_STARTED


def test_images_pipeline_marks_individual_assets(tmp_path: Path) -> None:
    registry = AssetRegistry(tmp_path)
    registry.ensure_image_slots(3)
    result = PipelineResult.success(
        "ok",
        artifacts=[
            "images/image_01.png",
            "images/image_02.png",
        ],
    )
    catalog = registry.record_pipeline_result("images", result)
    assert catalog.get("image_01").status is AssetStatus.READY
    assert catalog.get("image_02").status is AssetStatus.READY
    assert catalog.get("image_03").status is AssetStatus.NOT_STARTED


def test_workflow_snapshot_from_assets_not_folder_alone(tmp_path: Path) -> None:
    registry = AssetRegistry(tmp_path)
    registry.ensure_inventory(reconcile_disk=False)
    registry.set_status(
        "script",
        AssetStatus.READY,
        location="script/script.txt",
        generator="script",
    )
    snap = scan_workflow(tmp_path)
    assert snap.stage("script").state is StageState.COMPLETED
    assert snap.next_key == "production_sheet"
    assert snap.primary_action == "Generate Sheet"


def test_failed_pipeline_marks_failed(tmp_path: Path) -> None:
    registry = AssetRegistry(tmp_path)
    registry.ensure_inventory(reconcile_disk=False)
    registry.mark_pipeline_started("voice")
    catalog = registry.record_pipeline_result(
        "voice", PipelineResult.failed("boom", errors=["boom"])
    )
    voice = catalog.get("voice_over")
    assert voice is not None
    assert voice.status is AssetStatus.FAILED
