"""Provider and server connection status for Orion Navigator."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from core.database import Database


class ConnectionRow(QFrame):
    def __init__(self, name: str, purpose: str, status: str, tone: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("signalRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)
        mark = QLabel("⌁")
        mark.setObjectName("navigatorMark")
        mark.setFixedWidth(24)
        row.addWidget(mark)
        copy = QVBoxLayout()
        copy.setSpacing(1)
        title = QLabel(name)
        title.setObjectName("sectionTitle")
        detail = QLabel(purpose)
        detail.setProperty("role", "muted")
        detail.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(detail)
        row.addLayout(copy, 1)
        chip = QLabel(status)
        chip.setObjectName("chip")
        chip.setProperty("tone", tone)
        row.addWidget(chip)


class ConnectionsPanel(QWidget):
    settings_requested = pyqtSignal()

    def __init__(self, db: Database, config: Config, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._config = config
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 26)
        root.setSpacing(14)

        header = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(3)
        eyebrow = QLabel("ORION CONSTELLATION")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Connections")
        title.setObjectName("pageTitle")
        subtitle = QLabel("The metadata providers and media-server surfaces Orion can currently navigate with.")
        subtitle.setProperty("role", "muted")
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        header.addLayout(copy, 1)
        refresh = QPushButton("↻ Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        manage = QPushButton("Manage keys")
        manage.setObjectName("btn_accent")
        manage.clicked.connect(self.settings_requested.emit)
        header.addWidget(manage)
        root.addLayout(header)

        server = QFrame()
        server.setObjectName("card")
        sv = QVBoxLayout(server)
        sv.setContentsMargins(15, 14, 15, 14)
        sv.setSpacing(8)
        st = QLabel("Media server")
        st.setObjectName("sectionTitle")
        sv.addWidget(st)
        sh = QLabel("Orion is currently Jellyfin-compatible at the filesystem level; direct server reconciliation has not landed yet.")
        sh.setProperty("role", "muted")
        sh.setWordWrap(True)
        sv.addWidget(sh)
        self._server_rows = QVBoxLayout()
        self._server_rows.setSpacing(7)
        sv.addLayout(self._server_rows)
        root.addWidget(server)

        providers = QFrame()
        providers.setObjectName("card")
        pv = QVBoxLayout(providers)
        pv.setContentsMargins(15, 14, 15, 14)
        pv.setSpacing(8)
        pt = QLabel("Metadata providers")
        pt.setObjectName("sectionTitle")
        pv.addWidget(pt)
        ph = QLabel("Configured means a credential exists locally; it is not presented as a live network-health test.")
        ph.setProperty("role", "muted")
        ph.setWordWrap(True)
        pv.addWidget(ph)
        self._provider_rows = QVBoxLayout()
        self._provider_rows.setSpacing(7)
        pv.addLayout(self._provider_rows)
        root.addWidget(providers)
        root.addStretch()

    @staticmethod
    def _clear(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self) -> None:
        self._clear(self._server_rows)
        self._clear(self._provider_rows)

        self._server_rows.addWidget(ConnectionRow(
            "Jellyfin",
            "Folder naming and layout are Jellyfin-ready. Direct library discovery, refresh, and verification are the next server-integration step.",
            "FILESYSTEM MODE",
            "violet",
        ))
        self._server_rows.addWidget(ConnectionRow(
            "Emby / Plex",
            "No direct adapter is present in the current Orion codebase.",
            "NOT WIRED",
            "warn",
        ))

        providers = [
            ("TMDb", "Movie and TV metadata", "tmdb", True),
            ("AniList", "Anime metadata", "", False),
            ("AniDB", "Anime metadata fallback", "anidb_client", True),
            ("AudD", "Music recognition", "audd", True),
            ("MusicBrainz", "Music metadata", "", False),
            ("Open Library", "Book metadata", "", False),
        ]
        for name, purpose, service, needs_key in providers:
            if not needs_key:
                status, tone = "AVAILABLE", "good"
            elif self._config.has_api_key(service):
                status, tone = "CONFIGURED", "good"
            else:
                status, tone = "NEEDS KEY", "warn"
            self._provider_rows.addWidget(ConnectionRow(name, purpose, status, tone))

    def on_shown(self) -> None:
        self.refresh()
