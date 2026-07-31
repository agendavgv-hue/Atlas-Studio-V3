"""Shared backend status vocabulary for Forge, ComfyUI, and future image servers."""

from __future__ import annotations

from enum import Enum


class BackendStatus(str, Enum):
    """Live reachability of an image generation backend."""

    ONLINE = "online"
    OFFLINE = "offline"
    STARTING = "starting"

    @property
    def label(self) -> str:
        return {
            BackendStatus.ONLINE: "Online",
            BackendStatus.OFFLINE: "Offline",
            BackendStatus.STARTING: "Starting...",
        }[self]

    @property
    def dot(self) -> str:
        """Static round indicator — no animation."""
        return {
            BackendStatus.ONLINE: "●",
            BackendStatus.OFFLINE: "●",
            BackendStatus.STARTING: "●",
        }[self]

    @property
    def emoji(self) -> str:
        """Clear status icon for new users (static, no animation)."""
        return {
            BackendStatus.ONLINE: "🟢",
            BackendStatus.OFFLINE: "🔴",
            BackendStatus.STARTING: "🟠",
        }[self]

    @property
    def display_title(self) -> str:
        return {
            BackendStatus.ONLINE: "Forge Online",
            BackendStatus.OFFLINE: "Forge Offline",
            BackendStatus.STARTING: "Starting Forge...",
        }[self]

    @property
    def color_token(self) -> str:
        return {
            BackendStatus.ONLINE: "online",
            BackendStatus.OFFLINE: "offline",
            BackendStatus.STARTING: "starting",
        }[self]

