"""Reusable Channel Studio form helpers — labels, help icons, sliders, combos."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def section_intro(title: str, blurb: str) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 8)
    layout.setSpacing(4)
    head = QLabel(title)
    head.setObjectName("SectionLabel")
    body = QLabel(blurb)
    body.setObjectName("PageSubtitle")
    body.setWordWrap(True)
    layout.addWidget(head)
    layout.addWidget(body)
    return box


def help_button(text: str) -> QToolButton:
    btn = QToolButton()
    btn.setText("i")
    btn.setToolTip(text)
    btn.setAutoRaise(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedSize(22, 22)
    return btn


def labeled_row(label: str, widget: QWidget, help_text: str = "") -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    title = QLabel(label)
    title.setMinimumWidth(140)
    layout.addWidget(title)
    layout.addWidget(widget, stretch=1)
    if help_text:
        layout.addWidget(help_button(help_text))
    return row


def make_combo(options: list[tuple[str, str]], *, current: str = "") -> QComboBox:
    combo = QComboBox()
    for label, value in options:
        combo.addItem(label, value)
    if current:
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    return combo


def set_combo(combo: QComboBox, value: str) -> None:
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)


def combo_value(combo: QComboBox, default: str = "") -> str:
    data = combo.currentData()
    return str(data) if data is not None else default


def make_slider(value: float = 50.0, *, minimum: int = 0, maximum: int = 100) -> tuple[QSlider, QLabel]:
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(int(value))
    read = QLabel(str(int(value)))
    read.setMinimumWidth(28)
    read.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    slider.valueChanged.connect(lambda v: read.setText(str(v)))
    return slider, read


def slider_row(label: str, slider: QSlider, readout: QLabel, help_text: str = "") -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    title = QLabel(label)
    title.setMinimumWidth(140)
    layout.addWidget(title)
    layout.addWidget(slider, stretch=1)
    layout.addWidget(readout)
    if help_text:
        layout.addWidget(help_button(help_text))
    return row


def add_combo_row(
    form: QFormLayout,
    label: str,
    combo: QComboBox,
    help_text: str = "",
) -> None:
    wrap = QWidget()
    layout = QHBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(combo, stretch=1)
    if help_text:
        layout.addWidget(help_button(help_text))
    form.addRow(label, wrap)
