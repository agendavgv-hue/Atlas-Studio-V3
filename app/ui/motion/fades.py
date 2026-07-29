"""Lightweight opacity animations."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def fade_window(
    widget: QWidget,
    *,
    start: float,
    end: float,
    duration_ms: int = 160,
    finished: Callable[[], None] | None = None,
) -> QPropertyAnimation:
    widget.setWindowOpacity(start)
    animation = QPropertyAnimation(widget, b"windowOpacity", widget)
    animation.setDuration(duration_ms)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    if finished is not None:
        animation.finished.connect(finished)
    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def fade_widget(
    widget: QWidget,
    *,
    start: float,
    end: float,
    duration_ms: int = 160,
    finished: Callable[[], None] | None = None,
) -> QPropertyAnimation:
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    effect.setOpacity(start)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration_ms)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    if finished is not None:
        animation.finished.connect(finished)
    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation
