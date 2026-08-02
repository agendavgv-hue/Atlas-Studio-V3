"""Channel Studio sections — Personality, Rules, Goals, Advanced."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QDoubleSpinBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.channels.studio.models import (
    PERSONALITY_TRAITS,
    PRIORITY_LABELS,
    ChannelStudioPack,
    priority_label,
)
from app.creative.models.rules import CreativeRule, default_rules
from app.ui.pages.channel_studio.form_kit import (
    make_slider,
    section_intro,
    slider_row,
)


class PersonalitySection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._sliders: dict[str, object] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Channel Personality",
                "Set the emotional DNA every generator should obey — mystery, wonder, epic, and more.",
            )
        )
        defaults = {
            "mystery": 100,
            "wonder": 95,
            "history": 100,
            "science": 85,
            "adventure": 70,
            "luxury": 80,
            "darkness": 90,
            "fantasy": 10,
            "humor": 0,
            "fear": 30,
            "hope": 40,
            "epic": 90,
        }
        for trait in PERSONALITY_TRAITS:
            slider, readout = make_slider(float(defaults.get(trait, 50)))
            self._sliders[trait] = slider
            layout.addWidget(
                slider_row(
                    trait.title(),
                    slider,
                    readout,
                    f"How strongly {trait} should color every output.",
                )
            )
        layout.addStretch()

    def load_pack(self, pack: ChannelStudioPack) -> None:
        traits = pack.personality.traits or {}
        for trait, slider in self._sliders.items():
            slider.setValue(int(traits.get(trait, slider.value())))

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        pack.personality.traits = {
            trait: float(slider.value()) for trait, slider in self._sliders.items()
        }


class RulesSection(QWidget):
    _CATEGORIES = (
        ("visual", "Visual"),
        ("thumbnail", "Thumbnail"),
        ("story", "Story"),
        ("movie", "Movie"),
        ("voice", "Voice"),
        ("brand", "Brand"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._list = QListWidget()
        self._priority = QComboBox()
        for label, value in (
            ("Critical", "critical"),
            ("High", "high"),
            ("Medium", "medium"),
            ("Low", "low"),
        ):
            self._priority.addItem(label, value)
        self._list.currentItemChanged.connect(self._sync_priority)
        self._priority.currentIndexChanged.connect(self._apply_priority)
        hint = QLabel("Enable rules and set priority for the future AI Critic.")
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Creative Rules",
                "Guardrails for identity — grouped by Visual, Thumbnail, Story, Movie, Voice, Brand.",
            )
        )
        layout.addWidget(hint)
        layout.addWidget(self._list)
        layout.addWidget(QLabel("Selected rule priority"))
        layout.addWidget(self._priority)
        layout.addStretch()
        self._rules: list[CreativeRule] = []

    def load_pack(self, pack: ChannelStudioPack) -> None:
        self._rules = list(pack.rules or default_rules())
        self._list.clear()
        grouped = {cat: [] for cat, _ in self._CATEGORIES}
        other: list[CreativeRule] = []
        for rule in self._rules:
            if rule.category in grouped:
                grouped[rule.category].append(rule)
            else:
                other.append(rule)
        for cat, label in self._CATEGORIES:
            header = QListWidgetItem(f"— {label} —")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(header)
            for rule in grouped[cat]:
                self._add_rule_item(rule)
        if other:
            header = QListWidgetItem("— Other —")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(header)
            for rule in other:
                self._add_rule_item(rule)

    def _add_rule_item(self, rule: CreativeRule) -> None:
        item = QListWidgetItem(
            f"{rule.title}  [{priority_label(rule.priority).title()}] — {rule.description}"
        )
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        item.setCheckState(
            Qt.CheckState.Checked if rule.enabled else Qt.CheckState.Unchecked
        )
        item.setData(Qt.ItemDataRole.UserRole, rule.id)
        self._list.addItem(item)

    def _sync_priority(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None or not current.data(Qt.ItemDataRole.UserRole):
            return
        rule_id = str(current.data(Qt.ItemDataRole.UserRole))
        for rule in self._rules:
            if rule.id == rule_id:
                label = priority_label(rule.priority)
                idx = self._priority.findData(label)
                if idx >= 0:
                    self._priority.blockSignals(True)
                    self._priority.setCurrentIndex(idx)
                    self._priority.blockSignals(False)
                break

    def _apply_priority(self) -> None:
        item = self._list.currentItem()
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return
        rule_id = str(item.data(Qt.ItemDataRole.UserRole))
        label = str(self._priority.currentData() or "medium")
        value = PRIORITY_LABELS.get(label, 50)
        for rule in self._rules:
            if rule.id == rule_id:
                rule.priority = value
                item.setText(
                    f"{rule.title}  [{label.title()}] — {rule.description}"
                )
                break

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        enabled_ids = set()
        for i in range(self._list.count()):
            item = self._list.item(i)
            rid = item.data(Qt.ItemDataRole.UserRole)
            if rid and item.checkState() == Qt.CheckState.Checked:
                enabled_ids.add(str(rid))
        for rule in self._rules:
            rule.enabled = rule.id in enabled_ids
        pack.rules = list(self._rules)


class GoalsSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.uploads = QDoubleSpinBox()
        self.uploads.setRange(0, 30)
        self.subs = QSpinBox()
        self.subs.setRange(0, 100_000_000)
        self.views = QSpinBox()
        self.views.setRange(0, 2_000_000_000)
        self.ctr = QDoubleSpinBox()
        self.ctr.setRange(0, 100)
        self.retention = QDoubleSpinBox()
        self.retention.setRange(0, 100)
        self.rpm = QDoubleSpinBox()
        self.rpm.setRange(0, 1000)
        form = QFormLayout()
        form.addRow("Uploads per week", self.uploads)
        form.addRow("Subscriber goal", self.subs)
        form.addRow("View goal", self.views)
        form.addRow("CTR goal %", self.ctr)
        form.addRow("Retention goal %", self.retention)
        form.addRow("RPM goal", self.rpm)
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Goals",
                "Channel targets later used by Analytics — keep them ambitious but realistic.",
            )
        )
        layout.addLayout(form)
        layout.addStretch()

    def load_pack(self, pack: ChannelStudioPack) -> None:
        g = pack.goals
        self.uploads.setValue(g.uploads_per_week)
        self.subs.setValue(g.subscriber_goal)
        self.views.setValue(g.view_goal)
        self.ctr.setValue(g.ctr_goal)
        self.retention.setValue(g.retention_goal)
        self.rpm.setValue(g.rpm_goal)

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        g = pack.goals
        g.uploads_per_week = float(self.uploads.value())
        g.subscriber_goal = int(self.subs.value())
        g.view_goal = int(self.views.value())
        g.ctr_goal = float(self.ctr.value())
        g.retention_goal = float(self.retention.value())
        g.rpm_goal = float(self.rpm.value())


class AdvancedSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.path = QLabel("")
        self.path.setObjectName("PageSubtitle")
        self.path.setWordWrap(True)
        self.counts = QLabel("")
        self.counts.setObjectName("PageSubtitle")
        self.counts.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Advanced",
                "Storage paths and reference counts. AI, Learning, and Analytics arrive later.",
            )
        )
        layout.addWidget(self.path)
        layout.addWidget(self.counts)
        layout.addStretch()

    def load_pack(self, pack: ChannelStudioPack, *, root: str = "", counts: dict | None = None) -> None:
        self.path.setText(f"Studio folder: {root}")
        if counts:
            self.counts.setText(
                "References — "
                + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
            )

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        return
