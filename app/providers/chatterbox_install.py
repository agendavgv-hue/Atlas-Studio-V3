"""Chatterbox model install helpers — Atlas AI Models folder only."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from app.core import ai_storage
from app.providers.errors import ProviderError

logger = logging.getLogger(__name__)

CHATTERBOX_REPO_ID = "ResembleAI/chatterbox"
CHATTERBOX_ENGLISH_FILES: tuple[str, ...] = (
    "ve.safetensors",
    "t3_cfg.safetensors",
    "s3gen.safetensors",
    "tokenizer.json",
    "conds.pt",
)
CHATTERBOX_MODEL_SIZE_BYTES = int(3.2 * (1024**3))
CHATTERBOX_MODEL_SIZE_LABEL = "~3.2 GB"

ProgressCallback = Callable[[int, int, str], None]  # downloaded, total, message
CancelCheck = Callable[[], bool]


class ChatterboxModelMissingError(ProviderError):
    """Raised when Chatterbox weights are not present under the Atlas AI Models folder."""

    def __init__(
        self,
        message: str = "",
        *,
        model_dir: Path | None = None,
    ) -> None:
        directory = model_dir or ai_storage.chatterbox_dir()
        text = message or (
            "Chatterbox model not installed.\n\n"
            f"Model size: {CHATTERBOX_MODEL_SIZE_LABEL}\n"
            f"Download location: {directory}"
        )
        super().__init__(text)
        self.model_dir = directory


def chatterbox_model_dir(root: Path | None = None) -> Path:
    ai_storage.apply_ai_storage_environment(root)
    return ai_storage.chatterbox_dir(root)


def is_chatterbox_english_installed(root: Path | None = None) -> bool:
    directory = chatterbox_model_dir(root)
    return all((directory / name).is_file() for name in CHATTERBOX_ENGLISH_FILES)


def require_chatterbox_english(root: Path | None = None) -> Path:
    directory = chatterbox_model_dir(root)
    if not is_chatterbox_english_installed(root):
        raise ChatterboxModelMissingError(model_dir=directory)
    return directory


def download_chatterbox_english(
    root: Path | None = None,
    *,
    on_progress: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> Path:
    """Download English Chatterbox weights into ``{AI Models}/Chatterbox``."""
    ai_storage.apply_ai_storage_environment(root)
    dest = ai_storage.chatterbox_dir(root)
    dest.mkdir(parents=True, exist_ok=True)

    if is_chatterbox_english_installed(root):
        if on_progress:
            on_progress(CHATTERBOX_MODEL_SIZE_BYTES, CHATTERBOX_MODEL_SIZE_BYTES, "Already installed.")
        return dest

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise ProviderError(
            "huggingface_hub is required to download Chatterbox models. "
            "Install with: pip install huggingface_hub"
        ) from exc

    total = CHATTERBOX_MODEL_SIZE_BYTES
    started = time.monotonic()

    def _emit() -> None:
        if on_progress is None:
            return
        downloaded = sum(
            (dest / name).stat().st_size
            for name in CHATTERBOX_ENGLISH_FILES
            if (dest / name).is_file()
        )
        remaining = max(0, total - downloaded)
        elapsed = max(0.001, time.monotonic() - started)
        rate = downloaded / elapsed
        eta = (remaining / rate) if rate > 1 else None
        message = (
            f"Downloaded {ai_storage.format_bytes(downloaded)} of "
            f"{ai_storage.format_bytes(total)} · "
            f"remaining {ai_storage.format_bytes(remaining)} · "
            f"ETA {ai_storage.format_eta(eta)}"
        )
        on_progress(min(downloaded, total), total, message)

    if on_progress:
        on_progress(0, total, f"Starting download into {dest}…")

    for filename in CHATTERBOX_ENGLISH_FILES:
        if cancel_check is not None and cancel_check():
            raise ProviderError("Chatterbox model download was cancelled.")
        target = dest / filename
        if target.is_file() and target.stat().st_size > 0:
            _emit()
            continue
        logger.info("Downloading Chatterbox file %s → %s", filename, dest)
        if on_progress:
            on_progress(
                sum(
                    (dest / name).stat().st_size
                    for name in CHATTERBOX_ENGLISH_FILES
                    if (dest / name).is_file()
                ),
                total,
                f"Downloading {filename}…",
            )
        try:
            hf_hub_download(
                repo_id=CHATTERBOX_REPO_ID,
                filename=filename,
                local_dir=str(dest),
                local_dir_use_symlinks=False,
            )
        except TypeError:
            # Older huggingface_hub without local_dir_use_symlinks.
            hf_hub_download(
                repo_id=CHATTERBOX_REPO_ID,
                filename=filename,
                local_dir=str(dest),
            )
        _emit()

    if not is_chatterbox_english_installed(root):
        missing = [name for name in CHATTERBOX_ENGLISH_FILES if not (dest / name).is_file()]
        raise ProviderError(
            "Chatterbox download finished but required files are still missing: "
            + ", ".join(missing)
        )

    if on_progress:
        on_progress(total, total, "Chatterbox model installed.")
    return dest
