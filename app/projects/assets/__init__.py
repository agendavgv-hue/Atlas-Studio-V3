"""Project production assets — tracked inventory for Project Details."""

from app.projects.assets.catalog import CORE_ASSET_SPECS, make_image_asset
from app.projects.assets.models import (
    AssetCatalog,
    AssetStatus,
    AssetType,
    ProjectAsset,
)
from app.projects.assets.registry import AssetRegistry
from app.projects.assets.store import AssetStore, assets_path

__all__ = [
    "AssetCatalog",
    "AssetRegistry",
    "AssetStatus",
    "AssetStore",
    "AssetType",
    "CORE_ASSET_SPECS",
    "ProjectAsset",
    "assets_path",
    "make_image_asset",
]
