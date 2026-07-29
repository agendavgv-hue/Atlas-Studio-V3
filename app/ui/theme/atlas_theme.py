"""Atlas Studio dark theme."""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


# Deep studio palette — restrained, production-focused
COLORS = {
    "bg_deep": "#0E1116",
    "bg_panel": "#151A21",
    "bg_elevated": "#1C232D",
    "bg_hover": "#243040",
    "border": "#2A3441",
    "text": "#E8EEF5",
    "text_muted": "#8B9AAB",
    "accent": "#3D9CF0",
    "accent_dim": "#2A6FA8",
}


def build_palette() -> QPalette:
    palette = QPalette()
    bg = QColor(COLORS["bg_deep"])
    panel = QColor(COLORS["bg_panel"])
    text = QColor(COLORS["text"])
    muted = QColor(COLORS["text_muted"])
    accent = QColor(COLORS["accent"])
    border = QColor(COLORS["border"])

    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, panel)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["bg_elevated"]))
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["bg_elevated"]))
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, muted)
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["bg_elevated"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Light, border)
    palette.setColor(QPalette.ColorRole.Mid, border)
    palette.setColor(QPalette.ColorRole.Dark, bg)
    return palette


def stylesheet() -> str:
    c = COLORS
    return f"""
    QMainWindow, QWidget {{
        background-color: {c["bg_deep"]};
        color: {c["text"]};
        font-family: "Segoe UI", "Helvetica Neue", sans-serif;
        font-size: 13px;
    }}

    QLabel#SidebarLogo {{
        color: {c["text"]};
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 2px;
        padding: 20px 16px 24px 16px;
    }}

    QFrame#Sidebar {{
        background-color: {c["bg_panel"]};
        border-right: 1px solid {c["border"]};
    }}

    QPushButton[navButton="true"] {{
        background-color: transparent;
        color: {c["text_muted"]};
        border: none;
        border-radius: 6px;
        text-align: left;
        padding: 10px 14px;
        margin: 2px 10px;
        font-size: 13px;
        font-weight: 500;
    }}

    QPushButton[navButton="true"]:hover {{
        background-color: {c["bg_hover"]};
        color: {c["text"]};
    }}

    QPushButton[navButton="true"]:checked {{
        background-color: {c["bg_elevated"]};
        color: {c["text"]};
        border-left: 3px solid {c["accent"]};
        padding-left: 11px;
    }}

    QLabel#PageTitle {{
        color: {c["text"]};
        font-size: 22px;
        font-weight: 600;
    }}

    QLabel#PageSubtitle {{
        color: {c["text_muted"]};
        font-size: 13px;
    }}

    QFrame#PageFrame {{
        background-color: {c["bg_deep"]};
    }}

    QLineEdit {{
        background-color: {c["bg_panel"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 6px;
        padding: 8px 10px;
        selection-background-color: {c["accent"]};
    }}

    QListWidget {{
        background-color: {c["bg_panel"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 4px;
        outline: none;
    }}

    QListWidget::item {{
        padding: 10px 12px;
        border-radius: 4px;
    }}

    QListWidget::item:selected {{
        background-color: {c["bg_elevated"]};
        color: {c["text"]};
        border-left: 3px solid {c["accent"]};
    }}

    QPushButton {{
        background-color: {c["bg_elevated"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 6px;
        padding: 8px 14px;
    }}

    QPushButton:hover {{
        background-color: {c["bg_hover"]};
    }}
    """


def apply_theme(app: QApplication) -> None:
    app.setPalette(build_palette())
    app.setStyleSheet(stylesheet())
