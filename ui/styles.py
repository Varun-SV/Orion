"""Orion Navigator themes.

The desktop UI deliberately uses semantic object names instead of per-widget
hard-coded colours.  That keeps Nightfall and Starlight readable and makes it
possible to evolve the visual language without chasing inline styles.
"""
from __future__ import annotations

_THEMES = {
    "dark": {
        "bg": "#090c11",
        "sidebar": "#0b0f15",
        "panel": "#0e131b",
        "card": "#111823",
        "card2": "#0d141d",
        "input": "#0b1119",
        "hover": "#182232",
        "line": "#202a38",
        "text": "#f4f7fb",
        "muted": "#8d9aae",
        "muted2": "#627086",
        "accent": "#54c7ff",
        "accent_hover": "#79d4ff",
        "accent_bg": "rgba(84,199,255,0.12)",
        "violet": "#a9a0ff",
        "violet_bg": "rgba(169,160,255,0.12)",
        "success": "#54d69d",
        "success_bg": "rgba(84,214,157,0.12)",
        "warn": "#f5c66c",
        "warn_bg": "rgba(245,198,108,0.12)",
        "danger": "#ff7f87",
        "danger_bg": "rgba(255,127,135,0.12)",
        "legacy": "#0d1118",
        "selection": "rgba(84,199,255,0.18)",
    },
    "light": {
        "bg": "#f3f6fb",
        "sidebar": "#f8fafe",
        "panel": "#eef2f8",
        "card": "#ffffff",
        "card2": "#f7f9fc",
        "input": "#ffffff",
        "hover": "#e8eef7",
        "line": "#d9e1ec",
        "text": "#172033",
        "muted": "#5d6b7e",
        "muted2": "#7a8798",
        "accent": "#0077b6",
        "accent_hover": "#005f94",
        "accent_bg": "rgba(0,119,182,0.10)",
        "violet": "#6557c9",
        "violet_bg": "rgba(101,87,201,0.10)",
        "success": "#167a58",
        "success_bg": "rgba(22,122,88,0.10)",
        "warn": "#8a6100",
        "warn_bg": "rgba(138,97,0,0.10)",
        "danger": "#bd3f4c",
        "danger_bg": "rgba(189,63,76,0.10)",
        # Transitional host for existing detailed panels that still contain
        # a few legacy light-on-dark inline labels.  Keeping their canvas
        # dark guarantees readable text while the new shell can be Starlight.
        "legacy": "#10151e",
        "selection": "rgba(0,119,182,0.14)",
    },
}


def _build(theme: str) -> str:
    c = _THEMES[theme]
    return f"""
QMainWindow, QDialog {{
    background: {c['bg']};
}}
QWidget {{
    background: transparent;
    color: {c['text']};
    font-family: "Segoe UI", "SF Pro Text", Arial, sans-serif;
    font-size: 13px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QLabel[role="muted"] {{ color: {c['muted']}; }}
QLabel[role="subtle"] {{ color: {c['muted2']}; }}
QLabel#eyebrow {{
    color: {c['accent']};
    font-size: 10px;
    font-weight: 700;
}}
QLabel#pageTitle {{
    color: {c['text']};
    font-size: 26px;
    font-weight: 650;
}}
QLabel#sectionTitle {{
    color: {c['text']};
    font-size: 15px;
    font-weight: 600;
}}

/* App shell */
#appRoot {{ background: {c['bg']}; }}
#sidebar {{
    background: {c['sidebar']};
    border-right: 1px solid {c['line']};
}}
#topbar {{
    background: {c['sidebar']};
    border-bottom: 1px solid {c['line']};
}}
#brandName {{
    color: {c['text']};
    font-size: 15px;
    font-weight: 750;
}}
#brandTagline {{ color: {c['muted2']}; font-size: 10px; }}
#navGroupLabel {{
    color: {c['muted2']};
    font-size: 9px;
    font-weight: 700;
}}
QPushButton#navButton {{
    text-align: left;
    background: transparent;
    border: none;
    border-radius: 9px;
    padding: 9px 11px;
    color: {c['muted']};
    font-weight: 500;
}}
QPushButton#navButton:hover {{
    background: {c['hover']};
    color: {c['text']};
}}
QPushButton#navButton:checked {{
    background: {c['accent_bg']};
    color: {c['accent']};
    font-weight: 650;
}}
QLabel#navBadge {{
    background: {c['accent_bg']};
    color: {c['accent']};
    border: 1px solid {c['line']};
    border-radius: 8px;
    padding: 1px 5px;
    font-size: 9px;
    font-weight: 700;
}}
#workspaceSummary {{
    background: {c['card2']};
    border: 1px solid {c['line']};
    border-radius: 10px;
}}

/* Cards */
QFrame#card, QWidget#card {{
    background: {c['card']};
    border: 1px solid {c['line']};
    border-radius: 12px;
}}
QFrame#softCard, QWidget#softCard {{
    background: {c['card2']};
    border: 1px solid {c['line']};
    border-radius: 12px;
}}
QFrame#metricCard {{
    background: {c['card']};
    border: 1px solid {c['line']};
    border-radius: 12px;
}}
QLabel#metricLabel {{ color: {c['muted']}; font-size: 10px; font-weight: 600; }}
QLabel#metricValue {{ color: {c['text']}; font-size: 23px; font-weight: 650; }}
QLabel#metricValue[tone="accent"] {{ color: {c['accent']}; }}
QLabel#metricValue[tone="success"] {{ color: {c['success']}; }}
QLabel#metricValue[tone="warn"] {{ color: {c['warn']}; }}
QLabel#metricValue[tone="danger"] {{ color: {c['danger']}; }}
#navigatorBar {{
    background: {c['accent_bg']};
    border: 1px solid {c['line']};
    border-radius: 12px;
}}
#navigatorMark {{
    color: {c['accent']};
    font-size: 19px;
    font-weight: 700;
}}
#signalRow {{
    background: {c['card2']};
    border: 1px solid {c['line']};
    border-radius: 9px;
}}
QLabel#chip {{
    color: {c['muted']};
    background: {c['card2']};
    border: 1px solid {c['line']};
    border-radius: 8px;
    padding: 2px 7px;
    font-size: 10px;
}}
QLabel#chip[tone="good"] {{ color: {c['success']}; background: {c['success_bg']}; }}
QLabel#chip[tone="warn"] {{ color: {c['warn']}; background: {c['warn_bg']}; }}
QLabel#chip[tone="danger"] {{ color: {c['danger']}; background: {c['danger_bg']}; }}
QLabel#chip[tone="violet"] {{ color: {c['violet']}; background: {c['violet_bg']}; }}

/* Transitional host for existing functional media/settings panels. */
#legacySurface {{
    background: {c['legacy']};
    border: 1px solid {c['line']};
    border-radius: 12px;
}}

/* Buttons */
QPushButton {{
    background: {c['card2']};
    border: 1px solid {c['line']};
    border-radius: 7px;
    padding: 7px 13px;
    color: {c['muted']};
}}
QPushButton:hover {{
    background: {c['hover']};
    color: {c['text']};
}}
QPushButton:pressed {{ background: {c['panel']}; }}
QPushButton#btn_accent {{
    background: {c['accent']};
    border: 1px solid {c['accent']};
    color: #ffffff;
    font-weight: 650;
}}
QPushButton#btn_accent:hover {{ background: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
QPushButton#btn_danger {{
    background: {c['danger_bg']};
    border: 1px solid {c['line']};
    color: {c['danger']};
}}
QPushButton#themeButton {{ min-width: 96px; }}
QPushButton:disabled {{ color: {c['muted2']}; background: {c['panel']}; }}

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
    background: {c['input']};
    border: 1px solid {c['line']};
    border-radius: 7px;
    padding: 7px 10px;
    color: {c['text']};
    selection-background-color: {c['accent']};
    selection-color: #ffffff;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {c['accent']};
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {c['card']};
    color: {c['text']};
    border: 1px solid {c['line']};
    selection-background-color: {c['selection']};
}}

/* Lists / trees / tables */
QListWidget, QTreeWidget, QTableWidget {{
    background: {c['card']};
    color: {c['text']};
    border: 1px solid {c['line']};
    border-radius: 9px;
    outline: none;
    alternate-background-color: {c['card2']};
}}
QListWidget::item, QTreeWidget::item, QTableWidget::item {{
    padding: 6px 8px;
    color: {c['text']};
}}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background: {c['selection']};
    color: {c['text']};
}}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {c['hover']}; }}
QHeaderView::section {{
    background: {c['card2']};
    color: {c['muted']};
    border: none;
    border-bottom: 1px solid {c['line']};
    padding: 7px 9px;
    font-size: 10px;
    font-weight: 650;
}}

/* Tabs */
QTabWidget::pane {{ border: 1px solid {c['line']}; background: {c['card']}; border-radius: 9px; }}
QTabBar::tab {{
    background: transparent;
    color: {c['muted']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 13px;
}}
QTabBar::tab:selected {{ color: {c['accent']}; border-bottom: 2px solid {c['accent']}; }}
QTabBar::tab:hover {{ color: {c['text']}; }}

/* Progress */
QProgressBar {{
    background: {c['panel']};
    border: none;
    border-radius: 3px;
    min-height: 5px;
    max-height: 5px;
    color: transparent;
}}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}

/* Status / chrome */
QStatusBar {{
    background: {c['sidebar']};
    border-top: 1px solid {c['line']};
    color: {c['muted2']};
    font-size: 10px;
}}
QStatusBar QLabel {{ color: {c['muted2']}; }}
QSplitter::handle {{ background: {c['line']}; width: 1px; }}
QCheckBox {{ color: {c['muted']}; spacing: 7px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {c['line']};
    border-radius: 4px;
    background: {c['input']};
}}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}
QToolTip {{
    background: {c['card']};
    color: {c['text']};
    border: 1px solid {c['line']};
    padding: 5px 8px;
}}
QMessageBox {{ background: {c['card']}; color: {c['text']}; }}
QGroupBox {{
    border: 1px solid {c['line']};
    border-radius: 9px;
    margin-top: 12px;
    padding-top: 8px;
    color: {c['muted']};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {c['muted']}; }}
QScrollBar:vertical {{ background: transparent; width: 7px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['line']}; border-radius: 3px; min-height: 36px; }}
QScrollBar:horizontal {{ background: transparent; height: 7px; }}
QScrollBar::handle:horizontal {{ background: {c['line']}; border-radius: 3px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ background: none; border: none; }}
"""


def get_stylesheet(theme: str) -> str:
    """Return the requested Orion theme, falling back to Nightfall."""
    return _build(theme if theme in _THEMES else "dark")


DARK_STYLESHEET = get_stylesheet("dark")
LIGHT_STYLESHEET = get_stylesheet("light")
