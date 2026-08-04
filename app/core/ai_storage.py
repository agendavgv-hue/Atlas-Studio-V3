"""Atlas-owned AI model storage — paths, env bootstrap, and cache migration.

All Hugging Face / Chatterbox / Whisper / Forge / Ollama model caches must live
under the configured AI Models folder. Never use ``~/.cache/huggingface``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

DEFAULT_AI_MODELS_ROOT = Path(r"D:\AI\Models")

PROVIDER_SUBDIRS: tuple[str, ...] = (
    "Chatterbox",
    "HuggingFace",
    "Whisper",
    "Forge",
    "Ollama",
)

_HF_ENV_KEYS = (
    "HF_HOME",
    "HF_HUB_CACHE",
    "TRANSFORMERS_CACHE",
    "HUGGINGFACE_HUB_CACHE",
)


ProgressCallback = Callable[[str, float], None]  # message, fraction 0..1


def default_ai_models_root() -> Path:
    """Preferred Atlas AI Models root; fall back if the drive is missing."""
    preferred = DEFAULT_AI_MODELS_ROOT
    drive = preferred.drive
    if drive:
        try:
            if not Path(f"{drive}/").exists():
                return (Path.home() / "Atlas Studio" / "AI" / "Models").resolve()
        except OSError:
            return (Path.home() / "Atlas Studio" / "AI" / "Models").resolve()
    return preferred.resolve()


def peek_ai_models_root_from_disk() -> Path:
    """Read ``ai_models_root`` from config.json without requiring a full AppConfig load."""
    for path in _candidate_config_paths():
        try:
            if not path.is_file():
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        stored = raw.get("ai_models_root")
        if isinstance(stored, str) and stored.strip():
            try:
                return Path(stored).expanduser().resolve()
            except OSError:
                continue
    return default_ai_models_root()


def resolve_ai_models_root(config: object | None = None) -> Path:
    """Resolve the active AI Models root from config or disk."""
    if config is not None:
        value = getattr(config, "ai_models_root", None)
        if isinstance(value, Path):
            return value.expanduser().resolve()
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser().resolve()
    return peek_ai_models_root_from_disk()


def huggingface_dir(root: Path | None = None) -> Path:
    return (resolve_ai_models_root() if root is None else Path(root)).resolve() / "HuggingFace"


def chatterbox_dir(root: Path | None = None) -> Path:
    return (resolve_ai_models_root() if root is None else Path(root)).resolve() / "Chatterbox"


def whisper_dir(root: Path | None = None) -> Path:
    return (resolve_ai_models_root() if root is None else Path(root)).resolve() / "Whisper"


def forge_models_dir(root: Path | None = None) -> Path:
    return (resolve_ai_models_root() if root is None else Path(root)).resolve() / "Forge"


def ollama_models_dir(root: Path | None = None) -> Path:
    return (resolve_ai_models_root() if root is None else Path(root)).resolve() / "Ollama"


def ensure_ai_models_layout(root: Path | None = None) -> Path:
    """Create the AI Models root and provider subfolders. Returns the root."""
    resolved = (resolve_ai_models_root() if root is None else Path(root)).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    for name in PROVIDER_SUBDIRS:
        (resolved / name).mkdir(parents=True, exist_ok=True)
    return resolved


def apply_ai_storage_environment(root: Path | None = None) -> Path:
    """Point Hugging Face / Ollama env vars at the Atlas AI Models folder.

    Safe to call repeatedly. Must run before importing ``transformers``,
    ``huggingface_hub``, or Chatterbox model downloads.
    """
    resolved = ensure_ai_models_layout(root)
    hf = str(huggingface_dir(resolved))
    for key in _HF_ENV_KEYS:
        os.environ[key] = hf
    # Discourage accidental writes to the user home cache.
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    ollama = str(ollama_models_dir(resolved))
    os.environ["OLLAMA_MODELS"] = ollama
    logger.debug(
        "AI storage env applied | root=%s | HF_HOME=%s | OLLAMA_MODELS=%s",
        resolved,
        hf,
        ollama,
    )
    return resolved


def legacy_huggingface_cache() -> Path:
    """Default Windows / Unix Hugging Face cache Atlas must never use for new downloads."""
    return (Path.home() / ".cache" / "huggingface").resolve()


def legacy_hf_cache_has_content() -> bool:
    src = legacy_huggingface_cache()
    if not src.is_dir():
        return False
    try:
        next(src.iterdir())
        return True
    except StopIteration:
        return False
    except OSError:
        return False


@dataclass(frozen=True)
class MigrationResult:
    moved: int
    skipped: int
    source: Path
    destination: Path
    bytes_moved: int = 0


def migrate_legacy_huggingface_cache(
    destination: Path | None = None,
    *,
    on_progress: ProgressCallback | None = None,
) -> MigrationResult:
    """Move ``~/.cache/huggingface`` contents into the Atlas HuggingFace folder."""
    src = legacy_huggingface_cache()
    dest = (destination or huggingface_dir()).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    if not src.is_dir():
        if on_progress:
            on_progress("No legacy Hugging Face cache found.", 1.0)
        return MigrationResult(moved=0, skipped=0, source=src, destination=dest)

    try:
        entries = [p for p in src.iterdir()]
    except OSError as exc:
        raise OSError(f"Cannot read legacy Hugging Face cache at {src}: {exc}") from exc

    total = max(len(entries), 1)
    moved = 0
    skipped = 0
    bytes_moved = 0

    for index, item in enumerate(entries):
        target = dest / item.name
        fraction = (index + 1) / total
        if target.exists():
            skipped += 1
            if on_progress:
                on_progress(f"Skipped existing: {item.name}", fraction)
            continue
        if on_progress:
            on_progress(f"Moving {item.name}…", fraction * 0.95)
        size = _path_size(item)
        try:
            shutil.move(str(item), str(target))
        except OSError:
            # Cross-device move can fail mid-way; fall back to copy + remove.
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=False)
                shutil.rmtree(item, ignore_errors=True)
            else:
                shutil.copy2(item, target)
                item.unlink(missing_ok=True)
        moved += 1
        bytes_moved += size

    # Remove empty legacy tree when fully drained.
    try:
        if src.is_dir() and not any(src.iterdir()):
            src.rmdir()
    except OSError:
        pass

    if on_progress:
        on_progress("Migration complete.", 1.0)
    return MigrationResult(
        moved=moved,
        skipped=skipped,
        source=src,
        destination=dest,
        bytes_moved=bytes_moved,
    )


def format_bytes(num: float) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(max(0.0, num))
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0 or seconds == float("inf"):
        return "—"
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _path_size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            total = 0
            for child in path.rglob("*"):
                if child.is_file():
                    try:
                        total += child.stat().st_size
                    except OSError:
                        continue
            return total
    except OSError:
        return 0
    return 0


def _candidate_config_paths() -> list[Path]:
    """Likely AppConfig locations (Qt AppConfigLocation + common variants)."""
    paths: list[Path] = []
    for env_key in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(env_key)
        if not base:
            continue
        root = Path(base)
        paths.append(root / "Atlas Studio" / "Atlas Studio" / "config.json")
        paths.append(root / "Atlas Studio" / "config.json")
    # Optional: already-loaded Qt path when available.
    try:
        from app.core.app_config import bootstrap_config_path

        paths.insert(0, bootstrap_config_path())
    except Exception:  # noqa: BLE001
        pass
    # Deduplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        try:
            key = path.resolve()
        except OSError:
            key = path
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


# Re-export time for download ETA helpers used by UI workers.
monotonic = time.monotonic
