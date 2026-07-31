"""Forge / image-provider settings — all knobs configurable, none hardcoded in pipelines."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ForgeSettings:
    """Persisted Forge connection and generation parameters."""

    host: str = "127.0.0.1"
    port: int = 7860
    endpoint: str = "/sdapi/v1/txt2img"
    model: str = ""
    sampler: str = "DPM++ 2M Karras"
    scheduler: str = ""
    steps: int = 30
    cfg_scale: float = 7.0
    width: int = 1024
    height: int = 1024
    seed: int = -1
    negative_prompt: str = ""
    launch_path: str = ""
    auto_start_forge: bool = True
    close_forge_on_exit: bool = False

    @property
    def base_url(self) -> str:
        host = (self.host or "127.0.0.1").strip() or "127.0.0.1"
        return f"http://{host}:{int(self.port)}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> ForgeSettings:
        raw = data or {}
        return cls(
            host=str(raw.get("host") or "127.0.0.1").strip() or "127.0.0.1",
            port=_as_int(raw.get("port"), 7860),
            endpoint=str(raw.get("endpoint") or "/sdapi/v1/txt2img").strip()
            or "/sdapi/v1/txt2img",
            model=str(raw.get("model") or "").strip(),
            sampler=str(raw.get("sampler") or "DPM++ 2M Karras").strip()
            or "DPM++ 2M Karras",
            scheduler=str(raw.get("scheduler") or "").strip(),
            steps=max(1, _as_int(raw.get("steps"), 30)),
            cfg_scale=_as_float(raw.get("cfg_scale"), 7.0),
            width=max(64, _as_int(raw.get("width"), 1024)),
            height=max(64, _as_int(raw.get("height"), 1024)),
            seed=_as_int(raw.get("seed"), -1),
            negative_prompt=str(raw.get("negative_prompt") or ""),
            launch_path=str(raw.get("launch_path") or "").strip(),
            auto_start_forge=_as_bool(raw.get("auto_start_forge"), True),
            close_forge_on_exit=_as_bool(raw.get("close_forge_on_exit"), False),
        )


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default
