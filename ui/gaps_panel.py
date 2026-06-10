"""
Episode Gaps panel — finds missing episodes in the media-server library.

Loads every series from the connected Jellyfin/Emby server, and on
selection diffs the episodes the server has against the full episode
list from TMDb. Missing episodes are listed with season, number, and
title, so you know exactly what to hunt down next.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core import server_link
from core.config import Config
from core.database import Database
from api.tmdb import TMDbClient
from workers.server_worker import SeriesListWorker, GapAnalysisWorker


class GapsPanel(QWidget):
    def __init__(self, db: Database, config: Config, parent=None):
        super().__init__(parent)
        self._db     = db
        self._config = config
        self._list_worker: SeriesListWorker | None = None
        self._gap_worker:  GapAnalysisWorker | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel("Episode Gaps")
        title.setStyleSheet("font-size:17px; font-weight:500; color:#fff;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._load_btn = QPushButton("Load series from server")
        self._load_btn.setObjectName("btn_accent")
        self._load_btn.clicked.connect(self._load_series)
        hdr.addWidget(self._load_btn)
        v.addLayout(hdr)

        hint = QLabel(
            "Compares each series in your Jellyfin/Emby library against the "
            "full TMDb episode list and shows what's missing. Requires the "
            "server connection (Settings → Server) and a TMDb API key.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:rgba(255,255,255,0.35); font-size:12px;")
        v.addWidget(hint)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.4); font-size:11px;")
        v.addWidget(self._status_lbl)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:rgba(255,255,255,0.07);width:1px;}")

        self._series_list = QListWidget()
        self._series_list.setMinimumWidth(220)
        self._series_list.setMaximumWidth(320)
        self._series_list.setStyleSheet(
            "QListWidget{background:#131313;border:none;outline:none;}"
            "QListWidget::item{padding:7px 12px;}"
            "QListWidget::item:selected{background:rgba(0,164,220,0.15);"
            "border-right:2px solid #00a4dc;}"
            "QListWidget::item:hover{background:rgba(255,255,255,0.04);}")
        self._series_list.currentRowChanged.connect(self._on_series_selected)
        splitter.addWidget(self._series_list)

        self._tbl = QTableWidget(0, 3)
        self._tbl.setHorizontalHeaderLabels(["Season", "Episode", "Title"])
        h = self._tbl.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for col in (0, 1):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        splitter.addWidget(self._tbl)
        splitter.setSizes([260, 640])
        v.addWidget(splitter, 1)

    # ── Series list ────────────────────────────────────────────────────
    def _load_series(self) -> None:
        if self._list_worker and self._list_worker.isRunning():
            return
        client = server_link.get_client(self._db, self._config)
        if client is None:
            self._status_lbl.setText(
                "No server configured — add your Jellyfin/Emby URL and "
                "API key in Settings → Server.")
            return
        self._load_btn.setEnabled(False)
        self._status_lbl.setText("Loading series from server…")
        self._list_worker = SeriesListWorker(client)
        self._list_worker.loaded.connect(self._on_series_loaded)
        self._list_worker.error.connect(self._on_error)
        self._list_worker.start()

    def _on_series_loaded(self, series: list) -> None:
        self._load_btn.setEnabled(True)
        self._series_list.clear()
        self._tbl.setRowCount(0)
        for s in series:
            label = f"{s.name} ({s.year})" if s.year else s.name
            li = QListWidgetItem(f"  {label}")
            li.setData(Qt.ItemDataRole.UserRole, s)
            self._series_list.addItem(li)
        self._status_lbl.setText(
            f"{len(series)} series in library — select one to check for gaps."
            if series else "No series found in the server library.")

    # ── Gap analysis ───────────────────────────────────────────────────
    def _on_series_selected(self, row: int) -> None:
        li = self._series_list.item(row)
        if not li:
            return
        series = li.data(Qt.ItemDataRole.UserRole)
        if series is None:
            return
        if not self._config.has_api_key("tmdb"):
            self._status_lbl.setText(
                "Gap analysis needs a TMDb API key — add one in "
                "Settings → API Keys.")
            return
        client = server_link.get_client(self._db, self._config)
        if client is None:
            return
        if self._gap_worker and self._gap_worker.isRunning():
            self._gap_worker.progress.disconnect()
            self._gap_worker.complete.disconnect()
            self._gap_worker.error.disconnect()

        self._tbl.setRowCount(0)
        self._gap_worker = GapAnalysisWorker(
            client, TMDbClient(self._config.get_api_key("tmdb")),
            series.item_id, series.name, series.year)
        self._gap_worker.progress.connect(self._status_lbl.setText)
        self._gap_worker.complete.connect(
            lambda rows, total, name=series.name:
                self._on_gaps(name, rows, total))
        self._gap_worker.error.connect(self._on_error)
        self._gap_worker.start()

    def _on_gaps(self, name: str, rows: list, total: int) -> None:
        self._tbl.setRowCount(0)
        for r, (season, episode, title) in enumerate(rows):
            self._tbl.insertRow(r)
            self._tbl.setItem(r, 0, QTableWidgetItem(f"S{season:02d}"))
            self._tbl.setItem(r, 1, QTableWidgetItem(f"E{episode:02d}"))
            self._tbl.setItem(r, 2, QTableWidgetItem(title))
            self._tbl.item(r, 0).setForeground(QColor("#febc2e"))
        if rows:
            self._status_lbl.setText(
                f"{name}: missing {len(rows)} of {total} episode(s).")
        else:
            self._status_lbl.setText(
                f"{name}: complete — all {total} episode(s) present. ✓")

    def _on_error(self, msg: str) -> None:
        self._load_btn.setEnabled(True)
        self._status_lbl.setText(f"Error: {msg}")

    def on_shown(self) -> None:
        pass
