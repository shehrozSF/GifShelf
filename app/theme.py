import winreg

LIGHT = {
    "bg": "#f5f5f5",
    "bg_alt": "#ffffff",
    "fg": "#1a1a1a",
    "fg_muted": "#5a5a5a",
    "border": "#cccccc",
    "accent": "#3a6ea5",
    "accent_hover": "#2f5d8c",
    "accent_fg": "#ffffff",
    "hover": "#e8e8e8",
    "selected": "#dde7f0",
}

DARK = {
    "bg": "#202020",
    "bg_alt": "#2a2a2a",
    "fg": "#e6e6e6",
    "fg_muted": "#a0a0a0",
    "border": "#444444",
    "accent": "#5a8fc7",
    "accent_hover": "#73a3d6",
    "accent_fg": "#101010",
    "hover": "#333333",
    "selected": "#314152",
}


def is_system_dark() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except OSError:
        return False


def resolve_mode(mode: str) -> str:
    if mode == "system":
        return "dark" if is_system_dark() else "light"
    return mode


def build_stylesheet(mode: str) -> str:
    c = DARK if resolve_mode(mode) == "dark" else LIGHT
    return f"""
    QWidget {{
        background-color: {c['bg']};
        color: {c['fg']};
        font-family: "Segoe UI";
        font-size: 13px;
    }}

    QMainWindow, QDialog {{
        background-color: {c['bg']};
    }}

    QLineEdit, QTextEdit, QListWidget, QComboBox {{
        background-color: {c['bg_alt']};
        border: 1px solid {c['border']};
        border-radius: 2px;
        padding: 4px;
        color: {c['fg']};
    }}

    QPushButton {{
        background-color: {c['bg_alt']};
        border: 1px solid {c['border']};
        border-radius: 2px;
        padding: 5px 12px;
        color: {c['fg']};
    }}

    QPushButton:hover {{
        background-color: {c['hover']};
    }}

    QPushButton:pressed {{
        background-color: {c['selected']};
    }}

    QPushButton#primary {{
        background-color: {c['accent']};
        color: {c['accent_fg']};
        border: 1px solid {c['accent']};
    }}

    QPushButton#primary:hover {{
        background-color: {c['accent_hover']};
        border: 1px solid {c['accent_hover']};
    }}

    QPushButton:disabled {{
        color: {c['fg_muted']};
    }}

    QRadioButton {{
        spacing: 6px;
    }}

    QRadioButton::indicator {{
        width: 12px;
        height: 12px;
        border-radius: 7px;
        border: 1px solid {c['fg_muted']};
        background-color: {c['bg_alt']};
    }}

    QRadioButton::indicator:hover {{
        border: 1px solid {c['accent']};
    }}

    QRadioButton::indicator:checked {{
        border: 1px solid {c['accent']};
        background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
            stop:0 {c['accent_fg']}, stop:0.3 {c['accent_fg']}, stop:0.4 {c['accent']}, stop:1 {c['accent']});
    }}

    QRadioButton::indicator:disabled {{
        border: 1px solid {c['border']};
    }}

    QFrame#card {{
        background-color: {c['bg_alt']};
        border: 1px solid {c['border']};
        border-radius: 3px;
    }}

    QFrame#card QLabel {{
        background: transparent;
    }}

    QLabel#muted {{
        color: {c['fg_muted']};
    }}

    QListWidget::item {{
        padding: 4px;
    }}

    QListWidget::item:selected {{
        background-color: {c['selected']};
        color: {c['fg']};
    }}

    QScrollArea {{
        border: none;
    }}

    QSplitter::handle {{
        background-color: {c['border']};
    }}

    QMenuBar {{
        background-color: {c['bg']};
        border-bottom: 1px solid {c['border']};
    }}

    QMenuBar::item:selected {{
        background-color: {c['hover']};
    }}

    QMenu {{
        background-color: {c['bg_alt']};
        border: 1px solid {c['border']};
    }}

    QMenu::item:selected {{
        background-color: {c['hover']};
    }}

    QSlider::groove:horizontal {{
        border: 1px solid {c['border']};
        height: 4px;
        background: {c['bg_alt']};
    }}

    QSlider::handle:horizontal {{
        background: {c['accent']};
        border: none;
        width: 12px;
        margin: -5px 0;
        border-radius: 2px;
    }}

    QScrollBar:vertical {{
        background: {c['bg']};
        width: 12px;
    }}

    QScrollBar::handle:vertical {{
        background: {c['border']};
        min-height: 20px;
        border-radius: 2px;
    }}
    """
