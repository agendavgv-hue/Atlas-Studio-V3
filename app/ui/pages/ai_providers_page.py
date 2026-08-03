"""AI Providers settings — per-role Orchestrator bindings."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ai.roles import AIRole, ROLE_LABELS
from app.ai.settings import IMAGE_PROVIDER_IDS, TEXT_PROVIDER_IDS, RoleBinding
from app.atlas_application import AtlasApplication
from app.tasks.ollama_connection_worker import OllamaConnectionWorker


class AIProvidersPage(QWidget):
    """Choose which AI serves Creative Director, Image, Critic, SEO, Story."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AIProvidersPage")
        self._role_widgets: dict[str, tuple[QComboBox, QLineEdit, QComboBox, QLineEdit]] = {}
        self._thread: QThread | None = None
        self._worker: OllamaConnectionWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        title = QLabel("AI Providers")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Configure once in Settings. Production uses these bindings automatically."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        hosts = QGroupBox("Provider connections")
        hosts_form = QFormLayout(hosts)
        self._ollama_host = QLineEdit()
        self._ollama_host.setPlaceholderText("http://127.0.0.1:11434")
        self._openai_key = QLineEdit()
        self._openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_base = QLineEdit()
        self._anthropic_key = QLineEdit()
        self._anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._deepseek_key = QLineEdit()
        self._deepseek_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._deepseek_base = QLineEdit()
        hosts_form.addRow("Ollama host", self._ollama_host)
        ollama_row = QHBoxLayout()
        self._test_ollama_btn = QPushButton("Test Connection")
        self._test_ollama_btn.clicked.connect(self._test_ollama)
        ollama_row.addWidget(self._test_ollama_btn)
        ollama_row.addStretch()
        hosts_form.addRow("", ollama_row)
        self._ollama_status = QLabel("")
        self._ollama_status.setObjectName("PageSubtitle")
        self._ollama_status.setWordWrap(True)
        hosts_form.addRow("Status", self._ollama_status)
        hosts_form.addRow("OpenAI API key", self._openai_key)
        hosts_form.addRow("OpenAI base URL", self._openai_base)
        hosts_form.addRow("Anthropic API key", self._anthropic_key)
        hosts_form.addRow("DeepSeek API key", self._deepseek_key)
        hosts_form.addRow("DeepSeek base URL", self._deepseek_base)
        layout.addWidget(hosts)

        roles_box = QGroupBox("Role routing")
        roles_layout = QVBoxLayout(roles_box)
        for role in (
            AIRole.CREATIVE_DIRECTOR,
            AIRole.IMAGE_GENERATOR,
            AIRole.CRITIC,
            AIRole.SEO,
            AIRole.STORY,
        ):
            roles_layout.addWidget(self._build_role_card(role))
        layout.addWidget(roles_box)

        save = QPushButton("Save AI Orchestrator")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._save)
        layout.addWidget(save, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll)

    def _build_role_card(self, role: AIRole) -> QWidget:
        box = QGroupBox(ROLE_LABELS.get(role, role.value))
        form = QFormLayout(box)
        provider = QComboBox()
        ids = IMAGE_PROVIDER_IDS if role == AIRole.IMAGE_GENERATOR else TEXT_PROVIDER_IDS
        for pid in ids:
            provider.addItem(pid, pid)
        model = QLineEdit()
        model.setPlaceholderText("model id (e.g. qwen2.5:14b)")
        fallback = QComboBox()
        fallback.addItem("(none)", "")
        for pid in TEXT_PROVIDER_IDS:
            fallback.addItem(pid, pid)
        fallback_model = QLineEdit()
        fallback_model.setPlaceholderText("fallback model")
        form.addRow("Provider", provider)
        form.addRow("Model", model)
        if role != AIRole.IMAGE_GENERATOR:
            form.addRow("Fallback provider", fallback)
            form.addRow("Fallback model", fallback_model)
        self._role_widgets[role.value] = (provider, model, fallback, fallback_model)
        return box

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reload()

    def reload(self) -> None:
        app = self._app()
        if app is None:
            return
        ai = app.config.ai
        self._ollama_host.setText(ai.ollama_host)
        self._openai_key.setText(ai.openai_api_key)
        self._openai_base.setText(ai.openai_base_url)
        self._anthropic_key.setText(ai.anthropic_api_key)
        self._deepseek_key.setText(ai.deepseek_api_key)
        self._deepseek_base.setText(ai.deepseek_base_url)
        for role_key, (provider, model, fallback, fallback_model) in self._role_widgets.items():
            binding = ai.binding_for(role_key)
            idx = provider.findData(binding.provider)
            if idx < 0:
                idx = 0
            provider.setCurrentIndex(idx)
            model.setText(binding.model)
            fidx = fallback.findData(binding.fallback_provider)
            if fidx < 0:
                fidx = 0
            fallback.setCurrentIndex(fidx)
            fallback_model.setText(binding.fallback_model)

    def _save(self) -> None:
        app = self._app()
        if app is None:
            return
        ai = app.config.ai
        ai.ollama_host = self._ollama_host.text().strip() or "http://127.0.0.1:11434"
        ai.openai_api_key = self._openai_key.text().strip()
        ai.openai_base_url = self._openai_base.text().strip() or "https://api.openai.com/v1"
        ai.anthropic_api_key = self._anthropic_key.text().strip()
        ai.deepseek_api_key = self._deepseek_key.text().strip()
        ai.deepseek_base_url = (
            self._deepseek_base.text().strip() or "https://api.deepseek.com/v1"
        )
        for role_key, (provider, model, fallback, fallback_model) in self._role_widgets.items():
            ai.roles[role_key] = RoleBinding(
                provider=str(provider.currentData() or ""),
                model=model.text().strip(),
                fallback_provider=str(fallback.currentData() or ""),
                fallback_model=fallback_model.text().strip(),
            )
        # Keep legacy text_provider aligned with default / creative director preference.
        cd = ai.binding_for(AIRole.CREATIVE_DIRECTOR)
        if cd.provider in {"gemini", "ollama", "openai", "anthropic", "deepseek"}:
            app.config.text_provider = cd.provider if cd.provider != "qwen" else "ollama"
        img = ai.binding_for(AIRole.IMAGE_GENERATOR)
        if img.provider:
            app.config.image_provider = img.provider
        app.config.save()
        # Keep RuntimeManager / AIService endpoint in sync with the saved host.
        try:
            app.creative_workflow.set_ollama_endpoint(ai.ollama_host)
        except Exception:  # noqa: BLE001
            pass
        if hasattr(app, "rebuild_production_engine"):
            app.rebuild_production_engine()
        QMessageBox.information(self, "AI Orchestrator", "AI routing saved.")

    def _test_ollama(self) -> None:
        """Test Ollama via AIService → RuntimeManager.ensure_running (never direct HTTP)."""
        if self._thread is not None and self._thread.isRunning():
            return
        app = self._app()
        if app is None:
            return

        host = self._ollama_host.text().strip() or "http://127.0.0.1:11434"
        self._test_ollama_btn.setEnabled(False)
        self._ollama_status.setText("Starting AI runtime…")

        worker = OllamaConnectionWorker(
            app.creative_workflow,
            api_endpoint=host,
        )
        # Unparented thread — owned by this page via strong refs until finished.
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_ollama_progress)
        worker.finished.connect(self._on_ollama_finished)
        worker.failed.connect(self._on_ollama_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_ollama_thread_finished)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_ollama_progress(self, message: str) -> None:
        self._ollama_status.setText(message)

    def _on_ollama_finished(self, result: object) -> None:
        data = result if isinstance(result, dict) else {}
        ok = bool(data.get("ok"))
        status = str(data.get("status") or ("Connected" if ok else "Error"))
        endpoint = str(data.get("endpoint") or "")
        models = data.get("models") if isinstance(data.get("models"), list) else []
        message = str(data.get("message") or status)

        if ok:
            sample = ", ".join(str(m) for m in models[:8]) if models else "(no models pulled)"
            detail = f"Connected"
            if endpoint:
                detail += f" — {endpoint}"
            detail += f"\nModels: {sample}"
            self._ollama_status.setText(detail)
            QMessageBox.information(self, "Ollama", f"Connected\n\n{detail}")
        else:
            self._ollama_status.setText(f"Error — {message}")
            QMessageBox.warning(self, "Ollama", f"Error\n\n{message}")

    def _on_ollama_failed(self, message: str) -> None:
        self._ollama_status.setText(f"Error — {message}")
        QMessageBox.warning(self, "Ollama", f"Error\n\n{message}")

    def _on_ollama_thread_finished(self) -> None:
        self._test_ollama_btn.setEnabled(True)
        self._thread = None
        self._worker = None

    def _app(self) -> AtlasApplication | None:
        instance = AtlasApplication.instance()
        return instance if isinstance(instance, AtlasApplication) else None
