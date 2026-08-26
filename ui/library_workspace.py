"""Workflow-first host for Orion's existing per-library tools."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from core.database import Database
from ui.books_panel import BooksPanel
from ui.music_panel import MusicPanel
from ui.video_panel import VideoPanel


class LibraryWorkspacePanel(QWidget):
    """Keeps mature media-specific workflows while simplifying navigation."""

    content_changed = pyqtSignal()

    _DEFS = [
        ("Movies", "movies"),
        ("Series", "series"),
        ("Anime", "anime"),
        ("Anime Films", "anime_films"),
        ("Web Series", "web_series"),
        ("Music", "music"),
        ("Books", "books"),
    ]

    def __init__(self, db: Database, config: Config, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._config = config
        self._key_to_index = {key: i for i, (_, key) in enumerate(self._DEFS)}
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 26)
        root.setSpacing(14)

        header = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(3)
        eyebrow = QLabel("LIBRARY WORKSPACE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("All media")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Choose a library only when you need its specialised scanner, resolver, or organiser.")
        subtitle.setProperty("role", "muted")
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        header.addLayout(copy, 1)
        root.addLayout(header)

        self._tabs = QTabBar()
        self._tabs.setExpanding(False)
        self._tabs.setMovable(False)
        for label, _ in self._DEFS:
            self._tabs.addTab(label)
        self._tabs.currentChanged.connect(self._switch)
        root.addWidget(self._tabs)

        host = QFrame()
        host.setObjectName("legacySurface")
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(1, 1, 1, 1)
        host_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._panels = [
            VideoPanel(self._db, self._config, "Movies", ["movie"]),
            VideoPanel(self._db, self._config, "Series", ["series"]),
            VideoPanel(self._db, self._config, "Anime", ["anime"]),
            VideoPanel(self._db, self._config, "Anime Films", ["anime_film"]),
            VideoPanel(self._db, self._config, "Web Series", ["web_series"]),
            MusicPanel(self._db, self._config),
            BooksPanel(self._db, self._config),
        ]
        for panel in self._panels:
            self._stack.addWidget(panel)
        host_layout.addWidget(self._stack)
        root.addWidget(host, 1)

        # Existing video panels already expose scan_complete; route that event
        # back to the Navigator shell so counts and signals update immediately.
        for panel in self._panels[:5]:
            if hasattr(panel, "scan_complete"):
                panel.scan_complete.connect(self.content_changed.emit)

        self._tabs.setCurrentIndex(0)
        self._switch(0)

    def set_library(self, key: str) -> None:
        index = self._key_to_index.get(key)
        if index is None:
            return
        self._tabs.setCurrentIndex(index)
        self._switch(index)

    def _switch(self, index: int) -> None:
        if not 0 <= index < len(self._panels):
            return
        self._stack.setCurrentIndex(index)
        panel = self._panels[index]
        if hasattr(panel, "on_shown"):
            panel.on_shown()

    def on_shown(self) -> None:
        self._switch(self._stack.currentIndex())

    @property
    def video_panels(self) -> list[QWidget]:
        return self._panels[:5]
