"""AI Providers settings — per-role Orchestrator bindings."""

from __future__ import annotations

from PySide6.QtCore import Qt
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
from app.providers.errors import ProviderError
from app.providers.ollama import discover_ollama_models


class AIProvidersPage(QWidget):
    """Choose which AI serves Creative Director, Image, Critic, SEO, Story."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AIProvidersPage")
        self._role_widgets: dict[str, tuple[QComboBox, QLineEdit, QComboBox, QLineEdit]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        title = QLabel("AI Orchestrator")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Atlas routes specialized AIs per role. The LLM thinks. Forge draws. Atlas designs."
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
        test_ollama = QPushButton("Test Ollama")
        test_ollama.clicked.connect(self._test_ollama)
        ollama_row.addWidget(test_ollama)
        ollama_row.addStretch()
        hosts_form.addRow("", ollama_row)
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
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or not hasattr(app, "config"):
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
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or not hasattr(app, "config"):
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
        if hasattr(app, "rebuild_production_engine"):
            app.rebuild_production_engine()
        QMessageBox.information(self, "AI Orchestrator", "AI routing saved.")

    def _test_ollama(self) -> None:
        host = self._ollama_host.text().strip() or "http://127.0.0.1:11434"
        try:
            models = discover_ollama_models(host)
        except ProviderError as exc:
            QMessageBox.warning(self, "Ollama", str(exc))
            return
        sample = ", ".join(models[:8]) if models else "(no models pulled)"
        QMessageBox.information(
            self,
            "Ollama",
            f"Connected to {host}\nModels: {sample}",
        )
