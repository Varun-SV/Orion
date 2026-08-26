"""Orion Navigator main window.

Workflow-first application shell inspired by the approved Orion UI concept:
Overview → Review Queue → Operation Plan → Libraries → Connections → Activity.
Existing media-specific tools remain functional inside Libraries while the new
shell gives Orion a distinct navigation personality.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from core.database import Database
from ui.connections_panel import ConnectionsPanel
from ui.dashboard import DashboardPanel
from ui.library_workspace import LibraryWorkspacePanel
from ui.log_panel import LogPanel
from ui.operation_plan import OperationPlanPanel
from ui.review_queue import ReviewQueuePanel
from ui.settings_panel import SettingsPanel
from ui.styles import get_stylesheet


class ConstellationMark(QWidget):
    """Small Orion-inspired mark used in the shell and tray identity."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(38, 38)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cyan = QColor("#54c7ff")
        violet = QColor("#8f82ff")
        line = QPen(QColor(84, 199, 255, 100), 1.2)
        painter.setPen(line)
        points = [(7, 8), (13, 18), (19, 20), (26, 17), (31, 29)]
        for a, b in zip(points, points[1:]):
            painter.drawLine(a[0], a[1], b[0], b[1])
        painter.setPen(Qt.PenStyle.NoPen)
        for i, (x, y) in enumerate(points):
            painter.setBrush(violet if i in {0, 4} else cyan)
            radius = 3 if i in {1, 2, 3} else 2.5
            painter.drawEllipse(int(x - radius), int(y - radius), int(radius * 2), int(radius * 2))
        painter.end()


class NavButton(QPushButton):
    def __init__(self, glyph: str, text: str, parent=None) -> None:
        super().__init__(f"{glyph}   {text}", parent)
        self.setObjectName("navButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        self._badge = QLabel("", self)
        self._badge.setObjectName("navBadge")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setVisible(False)
        self._badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._badge.isVisible():
            self._badge.adjustSize()
            self._badge.move(self.width() - self._badge.width() - 9, (self.height() - self._badge.height()) // 2)

    def set_badge(self, count: int) -> None:
        if count > 0:
            self._badge.setText(str(count) if count < 100 else "99+")
            self._badge.adjustSize()
            self._badge.move(self.width() - self._badge.width() - 9, (self.height() - self._badge.height()) // 2)
            self._badge.raise_()
            self._badge.setVisible(True)
        else:
            self._badge.setVisible(False)


class LegacyHost(QFrame):
    """Readable transition surface for detailed panels not yet theme-tokenised."""

    def __init__(self, child: QWidget, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("legacySurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(child)
        self.child = child

    def on_shown(self) -> None:
        if hasattr(self.child, "on_shown"):
            self.child.on_shown()


class MainWindow(QMainWindow):
    def __init__(self, db: Database, config: Config) -> None:
        super().__init__()
        self._db = db
        self._config = config
        self._tray: QSystemTrayIcon | None = None
        self._theme = str(config.get_pref("theme", "dark"))
        if self._theme not in {"dark", "light"}:
            self._theme = "dark"
        self._setup_ui()
        self._setup_tray()
        self._restore_geometry()
        self._apply_theme(self._theme, persist=False)
        self._refresh_all()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Orion — Media Navigator")
        self.setMinimumSize(1100, 680)

        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._build_sidebar())
        shell.addWidget(self._build_workspace(), 1)
        self._build_status_bar()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(228)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 16, 14, 14)
        layout.setSpacing(5)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        brand_row.addWidget(ConstellationMark())
        brand_copy = QVBoxLayout()
        brand_copy.setSpacing(0)
        brand = QLabel("ORION")
        brand.setObjectName("brandName")
        tagline = QLabel("MEDIA NAVIGATOR")
        tagline.setObjectName("brandTagline")
        brand_copy.addWidget(brand)
        brand_copy.addWidget(tagline)
        brand_row.addLayout(brand_copy, 1)
        layout.addLayout(brand_row)
        layout.addSpacing(12)

        self._nav_buttons: list[NavButton] = []
        self._add_group_label(layout, "WORKSPACE")
        self._add_nav(layout, "✦", "Overview", 0)
        self._add_nav(layout, "⌖", "Review Queue", 1)
        self._add_nav(layout, "↗", "Operation Plans", 2)

        layout.addSpacing(7)
        self._add_group_label(layout, "LIBRARIES")
        self._add_nav(layout, "▦", "All Media", 3)
        self._library_summary = QLabel("Reading library map…")
        self._library_summary.setProperty("role", "subtle")
        self._library_summary.setWordWrap(True)
        self._library_summary.setContentsMargins(12, 2, 6, 6)
        layout.addWidget(self._library_summary)

        layout.addSpacing(7)
        self._add_group_label(layout, "SYSTEM")
        self._add_nav(layout, "⌁", "Connections", 4)
        self._add_nav(layout, "≡", "Activity", 5)
        self._add_nav(layout, "⚙", "Settings", 6)
        layout.addStretch()

        local = QFrame()
        local.setObjectName("workspaceSummary")
        lv = QVBoxLayout(local)
        lv.setContentsMargins(11, 9, 11, 9)
        lv.setSpacing(2)
        local_title = QLabel("✦  Local workspace")
        local_title.setObjectName("sectionTitle")
        self._workspace_meta = QLabel("—")
        self._workspace_meta.setProperty("role", "muted")
        lv.addWidget(local_title)
        lv.addWidget(self._workspace_meta)
        layout.addWidget(local)
        return sidebar

    @staticmethod
    def _add_group_label(layout: QVBoxLayout, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("navGroupLabel")
        label.setContentsMargins(10, 0, 0, 2)
        layout.addWidget(label)

    def _add_nav(self, layout: QVBoxLayout, glyph: str, text: str, index: int) -> None:
        button = NavButton(glyph, text)
        button.clicked.connect(lambda _checked=False, i=index: self._switch(i))
        self._nav_buttons.append(button)
        layout.addWidget(button)

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        outer = QVBoxLayout(workspace)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_topbar())

        self._stack = QStackedWidget()
        self._dashboard = DashboardPanel(self._db, self._config)
        self._review = ReviewQueuePanel(self._db, self._config)
        self._plan = OperationPlanPanel(self._db, self._config)
        self._libraries = LibraryWorkspacePanel(self._db, self._config)
        self._connections = ConnectionsPanel(self._db, self._config)
        self._activity = LegacyHost(LogPanel(self._db))
        self._settings = LegacyHost(SettingsPanel(self._db, self._config))
        self._pages = [
            self._dashboard,
            self._review,
            self._plan,
            self._libraries,
            self._connections,
            self._activity,
            self._settings,
        ]
        for page in self._pages:
            self._stack.addWidget(page)
        outer.addWidget(self._stack, 1)

        self._dashboard.review_requested.connect(lambda: self._switch(1))
        self._dashboard.plan_requested.connect(lambda: self._switch(2))
        self._dashboard.libraries_requested.connect(lambda: self._switch(3))
        self._review.open_library.connect(self._open_library)
        self._plan.libraries_requested.connect(lambda: self._switch(3))
        self._connections.settings_requested.connect(lambda: self._switch(6))
        self._libraries.content_changed.connect(self._refresh_all)

        self._switch(0)
        return workspace

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topbar")
        bar.setFixedHeight(58)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(9)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search signals and review queue…")
        self._search.setClearButtonEnabled(True)
        self._search.setMaximumWidth(470)
        self._search.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._search.returnPressed.connect(self._search_submit)
        layout.addWidget(self._search, 1)
        layout.addStretch()

        self._navigator_state = QLabel("✦  Navigator online")
        self._navigator_state.setObjectName("chip")
        self._navigator_state.setProperty("tone", "good")
        layout.addWidget(self._navigator_state)

        self._theme_btn = QPushButton()
        self._theme_btn.setObjectName("themeButton")
        self._theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self._theme_btn)

        scan = QPushButton("＋ Scan library")
        scan.setObjectName("btn_accent")
        scan.setToolTip("Open Libraries and choose the media scanner you want to run")
        scan.clicked.connect(lambda: self._switch(3))
        layout.addWidget(scan)
        return bar

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)
        self._status_lbl = QLabel("Ready")
        sb.addWidget(self._status_lbl)
        self._progress = QProgressBar()
        self._progress.setFixedWidth(220)
        self._progress.setVisible(False)
        sb.addPermanentWidget(self._progress)
        self._mode_lbl = QLabel("LOCAL-FIRST · ORION NAVIGATOR")
        sb.addPermanentWidget(self._mode_lbl)

    def _switch(self, index: int) -> None:
        if not 0 <= index < len(self._pages):
            return
        self._stack.setCurrentIndex(index)
        for i, button in enumerate(self._nav_buttons):
            button.setChecked(i == index)
        page = self._pages[index]
        if hasattr(page, "on_shown"):
            page.on_shown()
        if index in {0, 1, 2, 4}:
            self._refresh_counts()

    def _open_library(self, key: str) -> None:
        self._libraries.set_library(key)
        self._switch(3)

    def _search_submit(self) -> None:
        text = self._search.text().strip()
        self._switch(1)
        self._review.set_search(text)

    def _toggle_theme(self) -> None:
        self._apply_theme("light" if self._theme == "dark" else "dark")

    def _apply_theme(self, theme: str, persist: bool = True) -> None:
        self._theme = theme if theme in {"dark", "light"} else "dark"
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_stylesheet(self._theme))
        if persist:
            self._config.set_pref("theme", self._theme)
        if hasattr(self, "_theme_btn"):
            self._theme_btn.setText("☀  Starlight" if self._theme == "dark" else "☾  Nightfall")
            self._theme_btn.setToolTip(
                "Switch to Orion Starlight" if self._theme == "dark" else "Switch to Orion Nightfall"
            )

    def _refresh_all(self) -> None:
        self._dashboard.refresh()
        self._review.refresh()
        self._plan.refresh()
        self._connections.refresh()
        self._refresh_counts()
        self._refresh_workspace_summary()

    def _refresh_counts(self) -> None:
        self._review.refresh()
        pending = self._review.pending_count
        self._nav_buttons[1].set_badge(pending)
        scan_by_name = {i["name"]: i for i in self._db.get_scan_items()}
        active_video_choices = sum(
            1 for choice in self._db.get_all_rename_choices()
            if choice["original_name"] in scan_by_name
            and scan_by_name[choice["original_name"]]["status"] != "moved"
        )
        approved = (
            active_video_choices
            + sum(
                1 for i in self._db.get_music_items()
                if i["status"] != "moved" and self._db.get_music_rename_choice(i["source_path"])
            )
            + sum(
                1 for i in self._db.get_book_items()
                if i["status"] != "moved" and self._db.get_book_rename_choice(i["source_path"])
            )
        )
        self._nav_buttons[2].set_badge(1 if approved else 0)
        errors = self._db.get_stats()["errors"]
        self._navigator_state.setText("⚠  Check signals" if errors else "✦  Navigator online")
        self._navigator_state.setProperty("tone", "warn" if errors else "good")
        self._navigator_state.style().unpolish(self._navigator_state)
        self._navigator_state.style().polish(self._navigator_state)

    def _refresh_workspace_summary(self) -> None:
        sources = len(self._db.get_source_folders())
        destinations = len(self._db.get_destinations())
        stats = self._db.get_stats()
        self._library_summary.setText(
            f"{stats['total']} tracked items\n{stats['pending']} awaiting review"
        )
        self._workspace_meta.setText(
            f"{sources} source{'s' if sources != 1 else ''} · "
            f"{destinations} destination{'s' if destinations != 1 else ''}"
        )

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
        self._refresh_all()
        if self._tray:
            self._tray.setToolTip("Orion — Media Navigator")
            self._tray.showMessage("Orion", msg, QSystemTrayIcon.MessageIcon.Information, 4000)

    def set_status(self, msg: str) -> None:
        self._status_lbl.setText(msg)

    def _make_tray_icon(self) -> QIcon:
        pix = QPixmap(24, 24)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(84, 199, 255, 120), 1))
        points = [(5, 6), (9, 12), (13, 13), (17, 11), (20, 18)]
        for a, b in zip(points, points[1:]):
            painter.drawLine(a[0], a[1], b[0], b[1])
        painter.setPen(Qt.PenStyle.NoPen)
        for index, (x, y) in enumerate(points):
            painter.setBrush(QColor("#8f82ff") if index in {0, 4} else QColor("#54c7ff"))
            painter.drawEllipse(x - 2, y - 2, 4, 4)
        painter.end()
        return QIcon(pix)

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self._make_tray_icon(), self)
        self._tray.setToolTip("Orion — Media Navigator")
        menu = QMenu()
        menu.addAction("Open Orion", self.show_normal)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def show_normal(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._tray and self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "Orion",
                "Navigator remains active in the background. Right-click the tray icon to quit.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
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
        QApplication.quit()

    def _save_geometry(self) -> None:
        geo = self.geometry()
        self._config.save_geometry("main", {
            "x": geo.x(), "y": geo.y(), "w": geo.width(), "h": geo.height(),
        })

    def _restore_geometry(self) -> None:
        geometry = self._config.load_geometry("main")
        if geometry:
            self.setGeometry(geometry["x"], geometry["y"], geometry["w"], geometry["h"])
        else:
            self.resize(1240, 780)
            self._center()

    def _center(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        rect = screen.availableGeometry()
        self.move(
            rect.x() + (rect.width() - self.width()) // 2,
            rect.y() + (rect.height() - self.height()) // 2,
        )
