"""Persist Critic reports for the Learning Engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.creative.critic.report import CriticReport
from app.creative.critic.settings import CriticSettings
from app.creative.paths import channel_creative_dir

CRITIC_DIR = "critic"
SETTINGS_FILE = "critic_settings.json"
REPORTS_FILE = "critic_reports.json"


def critic_dir(data_root: Path, channel: str) -> Path:
    path = channel_creative_dir(data_root, channel) / CRITIC_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_settings(data_root: Path, channel: str) -> CriticSettings:
    path = critic_dir(data_root, channel) / SETTINGS_FILE
    if not path.is_file():
        settings = CriticSettings()
        save_settings(data_root, channel, settings)
        return settings
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CriticSettings()
    return CriticSettings.from_dict(raw if isinstance(raw, dict) else {})


def save_settings(data_root: Path, channel: str, settings: CriticSettings) -> Path:
    path = critic_dir(data_root, channel) / SETTINGS_FILE
    path.write_text(json.dumps(settings.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def append_report(
    data_root: Path,
    channel: str,
    report: CriticReport,
    *,
    max_reports: int = 200,
) -> Path:
    path = critic_dir(data_root, channel) / REPORTS_FILE
    entries = _read_entries(path)
    entries.append(report.to_dict())
    if max_reports > 0 and len(entries) > max_reports:
        entries = entries[-max_reports:]
    path.write_text(json.dumps({"reports": entries}, indent=2) + "\n", encoding="utf-8")
    return path


def read_reports(data_root: Path, channel: str) -> list[CriticReport]:
    path = critic_dir(data_root, channel) / REPORTS_FILE
    return [CriticReport.from_dict(item) for item in _read_entries(path)]


def _read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, dict) and isinstance(raw.get("reports"), list):
        return [item for item in raw["reports"] if isinstance(item, dict)]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []
