"""Canonical production asset definitions (future stages = add a row)."""

from __future__ import annotations

from dataclasses import dataclass

from app.projects.assets.models import AssetType, ProjectAsset, AssetStatus


@dataclass(frozen=True)
class AssetSpec:
    id: str
    label: str
    type: AssetType
    stage_key: str
    sort_index: int
    generator: str = ""
    visible: bool = True
    default_location: str = ""


# Core assets always present in a project inventory.
CORE_ASSET_SPECS: tuple[AssetSpec, ...] = (
    AssetSpec(
        "script",
        "Script",
        AssetType.SCRIPT,
        "script",
        10,
        generator="script",
        default_location="script/script.txt",
    ),
    AssetSpec(
        "production_sheet",
        "Production Sheet",
        AssetType.PRODUCTION_SHEET,
        "production_sheet",
        20,
        generator="production_sheet",
        default_location="script/production_sheet.txt",
    ),
    AssetSpec(
        "voice_over",
        "Voice-over",
        AssetType.VOICE,
        "voice",
        30,
        generator="voice",
        default_location="voice/voice.wav",
    ),
    AssetSpec(
        "movie",
        "Movie",
        AssetType.MOVIE,
        "movie",
        50,
        generator="movie",
        default_location="youtube_video/video.mp4",
    ),
    AssetSpec(
        "short_1",
        "Short 1",
        AssetType.SHORT,
        "shorts",
        60,
        generator="shorts",
        default_location="short/short_01.mp4",
    ),
    AssetSpec(
        "short_2",
        "Short 2",
        AssetType.SHORT,
        "shorts",
        61,
        generator="shorts",
        default_location="short/short_02.mp4",
    ),
    AssetSpec(
        "export_package",
        "Export Package",
        AssetType.EXPORT,
        "youtube_export",
        70,
        generator="export",
        default_location="youtube_video/video.mp4",
    ),
    # TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
    AssetSpec(
        "thumbnail",
        "Thumbnail",
        AssetType.THUMBNAIL,
        "thumbnail",
        45,
        generator="thumbnail",
        default_location="thumbnail/thumbnail.png",
        visible=False,
    ),
)


def image_asset_id(index: int) -> str:
    return f"image_{index:02d}"


def image_asset_label(index: int) -> str:
    return f"Image {index:02d}"


def make_image_asset(index: int, *, location: str = "") -> ProjectAsset:
    return ProjectAsset(
        id=image_asset_id(index),
        type=AssetType.IMAGE,
        label=image_asset_label(index),
        status=AssetStatus.NOT_STARTED,
        location=location or f"images/image_{index:02d}.png",
        generator="images",
        stage_key="images",
        sort_index=40 + index,
        visible=True,
    )


def make_core_asset(spec: AssetSpec) -> ProjectAsset:
    return ProjectAsset(
        id=spec.id,
        type=spec.type,
        label=spec.label,
        status=AssetStatus.NOT_STARTED,
        location=spec.default_location,
        generator=spec.generator,
        stage_key=spec.stage_key,
        sort_index=spec.sort_index,
        visible=spec.visible,
    )


# Map pipeline_id → primary asset id (non-image).
PIPELINE_TO_ASSET: dict[str, str] = {
    "script": "script",
    "production_sheet": "production_sheet",
    "voice": "voice_over",
    "movie": "movie",
    "shorts": "short_1",  # shorts also updates short_2 via artifacts
    "thumbnail": "thumbnail",
    "export": "export_package",
    "youtube_export": "export_package",
}
