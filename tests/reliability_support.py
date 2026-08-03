"""Shared helpers for the Atlas AI reliability suite."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas.ai.orchestrator import AIOrchestrator
from atlas.ai.services.ai_service import AIService
from atlas.ai.settings import AISettings
from atlas.core.service_registry import ServiceRegistry
from atlas.plugins.plugin_manager import PluginManager
from atlas.runtime.runtime_manager import RuntimeManager
from plugins.ollama.plugin import OllamaPlugin


def project_root() -> Path:
    return ROOT


def bootstrap_ai_stack() -> tuple[RuntimeManager, AIService, OllamaPlugin, AISettings]:
    """Load Ollama plugin + RuntimeManager + AIService (same path as production)."""
    settings = AISettings.load(ROOT)
    runtime_manager = RuntimeManager(install_root=ROOT, ai_settings=settings)
    orchestrator = AIOrchestrator()
    ai_service = AIService(
        orchestrator=orchestrator,
        model_settings=settings.models,
        runtime_manager=runtime_manager,
    )
    services = ServiceRegistry()
    services.register("ai", ai_service)
    services.register("runtime", runtime_manager)

    plugin = OllamaPlugin(
        install_root=ROOT,
        service_registry=services,
        runtime_manager=runtime_manager,
        ai_orchestrator=orchestrator,
        ai_service=ai_service,
        ai_settings=settings,
    )
    manager = PluginManager(install_root=ROOT)
    manager.load(plugin)
    manager.initialize(plugin.id)
    return runtime_manager, ai_service, plugin, settings


def ollama_available(runtime_manager: RuntimeManager | None = None) -> bool:
    """True when Ollama can be ensured running (installed + healthy or startable)."""
    try:
        rm = runtime_manager or bootstrap_ai_stack()[0]
        info = rm.ensure_running("ollama")
        return bool(info.is_running)
    except Exception:  # noqa: BLE001
        return False


def default_ollama_model(settings: AISettings | None = None) -> str:
    settings = settings or AISettings.load(ROOT)
    return (
        settings.models.model_for_role("creative_director")
        or settings.models.default_model
        or ""
    ).strip()


def wait_until(predicate, *, timeout_s: float, interval_s: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return bool(predicate())


def run_in_thread(fn, *args, **kwargs) -> tuple[threading.Thread, list[Any], list[BaseException]]:
    """Run ``fn`` in a daemon thread; return (thread, results, errors)."""
    results: list[Any] = []
    errors: list[BaseException] = []

    def _target() -> None:
        try:
            results.append(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    return thread, results, errors


def ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def living_qthreads() -> list[Any]:
    from PySide6.QtCore import QThread

    app = ensure_qapp()
    return [obj for obj in app.findChildren(QThread) if obj.isRunning()]
