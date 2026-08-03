"""Workflow pages — lazy exports so startup only pays for visited pages.

Thumbnail Review / Design Review / AI Workflow remain importable for V3.1
but are disconnected from the sidebar.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "DashboardPage",
    "ChannelsPage",
    "ChannelStudioPage",
    "ProjectsPage",
    "ProjectWorkspacePage",
    "AIWorkflowPage",
    "SettingsPage",
    "AIProvidersPage",
    "ThumbnailReviewPage",
    "DesignReviewPage",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "DashboardPage": ("app.ui.pages.dashboard_page", "DashboardPage"),
    "ChannelsPage": ("app.ui.pages.channels_page", "ChannelsPage"),
    "ChannelStudioPage": ("app.ui.pages.channel_studio", "ChannelStudioPage"),
    "ProjectsPage": ("app.ui.pages.projects_page", "ProjectsPage"),
    "ProjectWorkspacePage": (
        "app.ui.pages.project_workspace_page",
        "ProjectWorkspacePage",
    ),
    # TODO V3.1 — Restore Thumbnail Generator after new AI workflow.
    "AIWorkflowPage": ("app.ui.pages.ai_workflow_page", "AIWorkflowPage"),
    "SettingsPage": ("app.ui.pages.settings_page", "SettingsPage"),
    "AIProvidersPage": ("app.ui.pages.ai_providers_page", "AIProvidersPage"),
    "ThumbnailReviewPage": (
        "app.ui.pages.thumbnail_review_page",
        "ThumbnailReviewPage",
    ),
    "DesignReviewPage": ("app.ui.pages.design_review_page", "DesignReviewPage"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module

    module = import_module(module_name)
    value = getattr(module, attr)
    globals()[name] = value
    return value
