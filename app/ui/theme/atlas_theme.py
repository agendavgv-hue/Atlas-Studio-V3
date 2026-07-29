"""Atlas Studio dark theme — premium gold accent."""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


COLORS = {
    "bg_deep": "#0B0D10",
    "bg_panel": "#12151A",
    "bg_elevated": "#1A1F27",
    "bg_hover": "#242A33",
    "border": "#2C333D",
    "text": "#F4F1EA",
    "text_muted": "#9AA3AD",
    "accent": "#C6A75E",
    "accent_dim": "#8F7840",
    "accent_soft": "#3A3426",
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
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0B0D10"))
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
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 2.4px;
        padding: 22px 18px 8px 18px;
    }}

    QLabel#SidebarTagline {{
        color: {c["accent"]};
        font-size: 10px;
        letter-spacing: 1.6px;
        padding: 0 18px 20px 18px;
    }}

    QFrame#Sidebar {{
        background-color: {c["bg_panel"]};
        border-right: 1px solid {c["border"]};
    }}

    QPushButton[navButton="true"] {{
        background-color: transparent;
        color: {c["text_muted"]};
        border: none;
        border-radius: 8px;
        text-align: left;
        padding: 11px 14px;
        margin: 2px 12px;
        font-size: 13px;
        font-weight: 500;
    }}

    QPushButton[navButton="true"]:hover {{
        background-color: {c["bg_hover"]};
        color: {c["text"]};
    }}

    QPushButton[navButton="true"]:checked {{
        background-color: {c["accent_soft"]};
        color: {c["text"]};
        border-left: 3px solid {c["accent"]};
        padding-left: 11px;
    }}

    QLabel#PageTitle {{
        color: {c["text"]};
        font-size: 24px;
        font-weight: 600;
        letter-spacing: 0.2px;
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
        border-radius: 8px;
        padding: 9px 12px;
        selection-background-color: {c["accent"]};
        selection-color: #0B0D10;
    }}

    QLineEdit:focus {{
        border: 1px solid {c["accent_dim"]};
    }}

    QListWidget {{
        background-color: {c["bg_panel"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 10px;
        padding: 6px;
        outline: none;
    }}

    QListWidget::item {{
        padding: 11px 12px;
        border-radius: 6px;
        margin: 1px 0;
    }}

    QListWidget::item:hover {{
        background-color: {c["bg_hover"]};
    }}

    QListWidget::item:selected {{
        background-color: {c["accent_soft"]};
        color: {c["text"]};
        border-left: 3px solid {c["accent"]};
    }}

    QPushButton {{
        background-color: {c["bg_elevated"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 9px 16px;
    }}

    QPushButton:hover {{
        background-color: {c["bg_hover"]};
        border-color: {c["accent_dim"]};
    }}

    QPushButton#PrimaryButton {{
        background-color: {c["accent_soft"]};
        border: 1px solid {c["accent_dim"]};
        color: {c["text"]};
        padding: 10px 18px;
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: {c["bg_hover"]};
        border-color: {c["accent"]};
    }}

    QFrame#EmptyState {{
        background-color: {c["bg_panel"]};
        border: 1px solid {c["border"]};
        border-radius: 12px;
    }}

    QLabel#EmptyStateTitle {{
        color: {c["text"]};
        font-size: 18px;
        font-weight: 600;
    }}

    QLabel#EmptyStateMessage {{
        color: {c["text_muted"]};
        font-size: 13px;
    }}

    QWidget#SplashScreen {{
        background-color: {c["bg_deep"]};
        border: 1px solid {c["border"]};
        border-radius: 14px;
    }}

    QLabel#SplashTitle {{
        color: {c["text"]};
        font-size: 26px;
        font-weight: 600;
        letter-spacing: 1px;
    }}

    QLabel#SplashVersion {{
        color: {c["accent"]};
        font-size: 12px;
        letter-spacing: 1px;
    }}

    QLabel#SplashStatus {{
        color: {c["text_muted"]};
        font-size: 12px;
    }}

    QLabel#SplashSteps {{
        color: {c["text"]};
        font-size: 12px;
        line-height: 1.5;
        padding-left: 8px;
    }}

    QFrame#Toast {{
        background-color: {c["bg_elevated"]};
        border: 1px solid {c["accent_dim"]};
        border-radius: 10px;
    }}

    QLabel#ToastTitle {{
        color: {c["text"]};
        font-size: 13px;
        font-weight: 600;
    }}

    QLabel#ToastMessage {{
        color: {c["text_muted"]};
        font-size: 12px;
    }}

    QDialog {{
        background-color: {c["bg_deep"]};
    }}
    """


def apply_theme(app: QApplication) -> None:
    app.setPalette(build_palette())
    app.setStyleSheet(stylesheet())
