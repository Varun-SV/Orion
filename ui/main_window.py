"""
Orion — Main application window.
Icon sidebar + QStackedWidget panels + system tray + status bar.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStackedWidget, QLabel, QProgressBar,
    QStatusBar, QSystemTrayIcon, QMenu, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor

from core.config import Config
from core.database import Database
from ui.dashboard import DashboardPanel
from ui.video_panel import VideoPanel
from ui.music_panel import MusicPanel
from ui.books_panel import BooksPanel
from ui.gaps_panel import GapsPanel
from ui.settings_panel import SettingsPanel
from ui.log_panel import LogPanel


def _make_icon(glyph: str, size: int = 22) -> QIcon:
    """Render a Tabler-icon glyph into a QIcon (fallback text icon)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    return QIcon(pix)


class SidebarButton(QPushButton):
    def __init__(self, icon_char: str, tooltip: str, parent=None):
        super().__init__(icon_char, parent)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFixedSize(QSize(44, 44))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._badge = QLabel("", self)
        self._badge.setStyleSheet(
            "background:#ff453a; border-radius:7px; color:#fff;"
            "font-size:8px; font-weight:bold; padding:1px 3px;")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setVisible(False)
        self._badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_badge(self, count: int) -> None:
        if count > 0:
            self._badge.setText(str(count) if count < 100 else "99+")
            self._badge.adjustSize()
            self._badge.move(self.width() - self._badge.width() - 2, 2)
            self._badge.raise_()
            self._badge.setVisible(True)
        else:
            self._badge.setVisible(False)


class MainWindow(QMainWindow):
    def __init__(self, db: Database, config: Config) -> None:
        super().__init__()
        self._db     = db
        self._config = config
        self._panels: list[QWidget] = []
        self._tray:   QSystemTrayIcon | None = None
        self._setup_ui()
        self._setup_tray()
        self._restore_geometry()

    # ── UI construction ────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        self.setWindowTitle("Orion — Media Library Organizer")
        self.setMinimumSize(1000, 640)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_content(), 1)

        self._build_status_bar()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(52)
        v = QVBoxLayout(sidebar)
        v.setContentsMargins(7, 14, 7, 14)
        v.setSpacing(4)
        v.setAlignment(Qt.AlignmentFlag.AlignTop)

        # App icon at top
        logo = QLabel("✦")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(36)
        logo.setStyleSheet("color: #00a4dc; font-size: 20px; margin-bottom: 8px;")
        v.addWidget(logo)

        # Panel indices: 0=Dashboard 1=Movies 2=Series 3=Anime 4=AnimeFilms
        #                5=WebSeries 6=Music 7=Books 8=Gaps 9=Settings 10=Log
        defs = [
            ("⊞",  "Dashboard",    0),
            ("▶",  "Movies",       1),
            ("☰",  "Series",       2),
            ("◈",  "Anime",        3),
            ("◼",  "Anime Films",  4),
            ("⌂",  "Web Series",   5),
            ("♪",  "Music",        6),
            ("📖", "Books",        7),
            ("▦",  "Episode Gaps", 8),
            ("⚙",  "Settings",     9),
        ]
        self._nav_buttons: list[QPushButton] = []
        for glyph, tip, idx in defs:
            btn = SidebarButton(glyph, tip)
            btn.setFixedSize(QSize(44, 44))   # slightly smaller to fit 9 buttons
            btn.clicked.connect(lambda _, i=idx: self._switch(i))
            self._nav_buttons.append(btn)
            v.addWidget(btn)

        v.addStretch()

        log_btn = SidebarButton("≡", "Activity log")
        log_btn.setFixedSize(QSize(44, 44))
        log_btn.clicked.connect(lambda: self._switch(10))
        self._nav_buttons.append(log_btn)
        v.addWidget(log_btn)
        return sidebar

    def _build_content(self) -> QWidget:
        self._stack = QStackedWidget()

        dashboard  = DashboardPanel(self._db, self._config)
        movies     = VideoPanel(self._db, self._config,
                                "Movies",     ["movie"])
        series     = VideoPanel(self._db, self._config,
                                "Series",     ["series"])
        anime      = VideoPanel(self._db, self._config,
                                "Anime",      ["anime"])
        anime_film = VideoPanel(self._db, self._config,
                                "Anime Films", ["anime_film"])
        web_series = VideoPanel(self._db, self._config,
                                "Web Series",  ["web_series"])
        music      = MusicPanel(self._db, self._config)
        books      = BooksPanel(self._db, self._config)
        gaps       = GapsPanel(self._db, self._config)
        settings   = SettingsPanel(self._db, self._config)
        log        = LogPanel(self._db)

        self._panels = [dashboard, movies, series, anime, anime_film,
                        web_series, music, books, gaps, settings, log]
        for p in self._panels:
            self._stack.addWidget(p)

        # Refresh dashboard after any per-panel scan completes
        for panel in (movies, series, anime, anime_film, web_series):
            panel.scan_complete.connect(dashboard.refresh)
            panel.scan_complete.connect(self._update_badges)

        self._switch(0)
        self._update_badges()
        return self._stack

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 11px;")
        sb.addWidget(self._status_lbl)

        self._progress   = QProgressBar()
        self._progress.setFixedWidth(220)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        sb.addPermanentWidget(self._progress)

        self._api_lbl = QLabel()
        self._api_lbl.setStyleSheet("color: rgba(255,255,255,0.25); font-size: 11px; margin-right: 8px;")
        sb.addPermanentWidget(self._api_lbl)
        self._refresh_api_status()

    def _make_tray_icon(self) -> QIcon:
        """Create a simple Jellyfin-blue dot icon programmatically."""
        from PyQt6.QtGui import QPainter, QBrush
        pix = QPixmap(22, 22)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor("#00a4dc")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 18, 18)
        # Three belt-star dots (Orion motif)
        p.setBrush(QBrush(QColor("#ffffff")))
        for x in (6, 11, 16):
            p.drawEllipse(x, 10, 3, 3)
        p.end()
        return QIcon(pix)

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self._make_tray_icon(), self)
        self._tray.setToolTip("Orion — Media Library Organizer")

        menu = QMenu()
        menu.addAction("Open Orion",     self.show_normal)
        menu.addSeparator()
        menu.addAction("Quit",           self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    # ── Navigation ─────────────────────────────────────────────────────
    def _switch(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        panel = self._panels[index] if index < len(self._panels) else None
        if hasattr(panel, "on_shown"):
            panel.on_shown()

    # ── Progress helpers (called by workers) ───────────────────────────
    def show_progress(self, value: int, maximum: int, msg: str = "") -> None:
        self._progress.setMaximum(maximum)
        self._progress.setValue(value)
        self._progress.setVisible(True)
        if msg:
            self._status_lbl.setText(msg)
        if self._tray:
            pct = int(value / maximum * 100) if maximum else 0
            self._tray.setToolTip(f"Orion — {pct}% ({msg})")

    def hide_progress(self, msg: str = "Ready") -> None:
        self._progress.setVisible(False)
        self._status_lbl.setText(msg)
        if self._tray:
            self._tray.setToolTip("Orion — Media Library Organizer")
            self._tray.showMessage("Orion", msg,
                                   QSystemTrayIcon.MessageIcon.Information, 4000)

    def set_status(self, msg: str) -> None:
        self._status_lbl.setText(msg)

    # ── API status ─────────────────────────────────────────────────────
    def _refresh_api_status(self) -> None:
        parts = []
        if self._config.has_api_key("tmdb"):
            parts.append("TMDb ✓")
        if self._config.has_api_key("anidb_client"):
            parts.append("AniDB ✓")
        parts.append("AniList ✓")
        if self._config.has_api_key("audd"):
            parts.append("AudD ✓")
        from core import server_link
        if server_link.is_configured(self._db, self._config):
            stype = self._db.setting_get("server_type", "jellyfin")
            parts.append(("Emby" if stype == "emby" else "Jellyfin") + " ✓")
        self._api_lbl.setText("  ".join(parts))

    def update_api_status(self) -> None:
        self._refresh_api_status()

    def _update_badges(self) -> None:
        resolved = {r["original_name"] for r in self._db.get_all_rename_choices()}
        # Nav buttons 1–5 correspond to the 5 video panels (panels[1]–panels[5])
        for nav_idx in range(1, 6):
            panel = self._panels[nav_idx]
            if not hasattr(panel, "_media_types"):
                continue
            items = self._db.get_scan_items_for_media_types(panel._media_types)
            pending = sum(
                1 for i in items
                if i["name"] not in resolved and i["status"] != "moved"
            )
            self._nav_buttons[nav_idx].set_badge(pending)

    # ── Window management ──────────────────────────────────────────────
    def show_normal(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def closeEvent(self, event) -> None:
        if self._tray and self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "Orion", "Running in the background. Right-click the tray icon to quit.",
                QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            self._save_geometry()
            event.accept()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_normal()

    def _quit(self) -> None:
        self._save_geometry()
        import sys
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def _save_geometry(self) -> None:
        geo = self.geometry()
        self._config.save_geometry("main", {
            "x": geo.x(), "y": geo.y(),
            "w": geo.width(), "h": geo.height(),
        })

    def _restore_geometry(self) -> None:
        g = self._config.load_geometry("main")
        if g:
            self.setGeometry(g["x"], g["y"], g["w"], g["h"])
        else:
            self.resize(1100, 700)
            self._center()

    def _center(self) -> None:
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )
