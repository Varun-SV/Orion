"""
VideoPanel — reusable scan + rename + move panel for a single video media type.

Instantiated once per media type (Movies, Series, Anime, Anime Films, Web Series).
Each panel scans only the categories matching its media_types list, shows only
those items in the left list, and moves them to the appropriate destination.
"""
from __future__ import annotations
import io, threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QScrollArea,
    QSplitter, QProgressBar, QLineEdit, QInputDialog,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDialog,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPixmap, QImage

from core.config import Config
from core.database import Database
from core.renamer import Renamer
from core.utils import sanitize_windows_name
from api.tmdb import TMDbClient, Candidate
from api.anilist import AniListClient
from api.anidb import AniDBClient
from workers.api_worker import ApiWorker
from workers.move_worker import MoveWorker
from workers.scan_worker import ScanWorker
from workers.batch_approve_worker import BatchApproveWorker


class _PosterSignal(QObject):
    ready = pyqtSignal(str, bytes)


class CandidateCard(QFrame):
    selected = pyqtSignal(object)

    def __init__(self, candidate: Candidate, with_year: bool, parent=None):
        super().__init__(parent)
        self._candidate = candidate
        self.setFixedSize(116, 210)
        self.setObjectName("candidate_card")
        self.setStyleSheet(
            "#candidate_card{background:#1e1e1e;"
            "border:1.5px solid rgba(255,255,255,0.1);border-radius:8px;}"
            "#candidate_card:hover{border-color:#00a4dc;"
            "background:#252525;cursor:pointer;}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(5, 5, 5, 6)
        v.setSpacing(4)

        self._poster = QLabel("🎬")
        self._poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster.setFixedSize(QSize(106, 156))
        self._poster.setStyleSheet(
            "background:#161616;border-radius:5px;"
            "font-size:28px;color:rgba(255,255,255,0.15);")
        v.addWidget(self._poster)

        display = candidate.display(with_year)
        rom = candidate.extra.get("romaji", "")
        text = display + (f"\n{rom}" if rom and rom != candidate.name else "")
        name_lbl = QLabel(text)
        name_lbl.setWordWrap(True)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.7);font-size:10px;line-height:1.4;")
        name_lbl.setMaximumWidth(106)
        v.addWidget(name_lbl)
        v.addStretch()

        if candidate.poster_url:
            self._load_poster(candidate.poster_url)

    def _load_poster(self, url: str) -> None:
        sig = _PosterSignal(self)
        sig.ready.connect(self._on_poster)
        def _fetch():
            try:
                import requests
                sig.ready.emit(url, requests.get(url, timeout=6).content)
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_poster(self, _url: str, data: bytes) -> None:
        try:
            from PIL import Image
            img  = Image.open(io.BytesIO(data)).convert("RGB").resize((106, 156))
            qimg = QImage(img.tobytes(), 106, 156, 106 * 3,
                          QImage.Format.Format_RGB888)
            self._poster.setPixmap(QPixmap.fromImage(qimg))
            self._poster.setText("")
        except Exception:
            pass

    def highlight(self, on: bool) -> None:
        color = "#00a4dc" if on else "rgba(255,255,255,0.1)"
        self.setStyleSheet(
            f"#candidate_card{{background:{'#1a2a34' if on else '#1e1e1e'};"
            f"border:2px solid {color};border-radius:8px;}}")

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self._candidate)
        super().mousePressEvent(event)


class VideoPanel(QWidget):
    """Merged scan + rename + move panel for one video media type group."""

    scan_complete = pyqtSignal()   # emitted after every scan; connect to dashboard

    def __init__(self, db: Database, config: Config,
                 panel_title: str,
                 media_types: list[str],
                 parent=None) -> None:
        super().__init__(parent)
        self._db           = db
        self._config       = config
        self._panel_title  = panel_title
        self._media_types  = media_types

        self._items:        list[dict] = []
        self._current:      dict | None = None
        self._cards:        list[CandidateCard] = []
        self._suggestions:  list[dict] = []
        self._renamer:      Renamer | None = None

        self._scan_worker:  ScanWorker | None = None
        self._api_worker:   ApiWorker | None = None
        self._move_worker:  MoveWorker | None = None
        self._batch_worker: BatchApproveWorker | None = None

        self._setup_ui()

    # ── UI construction ────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ── Rename toolbar (dark bar at top) ──────────────────────────
        toolbar = QWidget()
        toolbar.setStyleSheet(
            "background:#151515;border-bottom:1px solid rgba(255,255,255,0.07);")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(16, 10, 16, 10)
        tl.setSpacing(10)

        self._prog_lbl = QLabel("No items")
        self._prog_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.45);font-size:12px;")
        tl.addWidget(self._prog_lbl)
        self._prog_bar = QProgressBar()
        self._prog_bar.setFixedHeight(3)
        self._prog_bar.setTextVisible(False)
        tl.addWidget(self._prog_bar, 1)

        self._dry_run_chk = QCheckBox("Dry run")
        self._dry_run_chk.setToolTip(
            "Preview moves without touching the filesystem")
        tl.addWidget(self._dry_run_chk)
        self._inplace_chk = QCheckBox("In-place")
        self._inplace_chk.setToolTip(
            "Reorganise inside the source folder instead of moving to destination")
        tl.addWidget(self._inplace_chk)

        self._approve_btn = QPushButton("Approve all auto-matched")
        self._approve_btn.setObjectName("btn_accent")
        self._approve_btn.clicked.connect(self._approve_all_auto)
        tl.addWidget(self._approve_btn)
        self._move_btn = QPushButton("Move all resolved →")
        self._move_btn.clicked.connect(self._start_move)
        tl.addWidget(self._move_btn)
        v.addWidget(toolbar)

        # ── Scan bar ──────────────────────────────────────────────────
        scan_bar = QWidget()
        scan_bar.setStyleSheet(
            "background:#121212;border-bottom:1px solid rgba(255,255,255,0.04);")
        sl = QHBoxLayout(scan_bar)
        sl.setContentsMargins(16, 8, 16, 8)
        sl.setSpacing(8)

        self._scan_btn = QPushButton("Scan")
        self._scan_btn.setObjectName("btn_accent")
        self._scan_btn.clicked.connect(lambda: self._start_scan(deep=False))
        sl.addWidget(self._scan_btn)
        self._deep_btn = QPushButton("Deep scan  (+guessit)")
        self._deep_btn.clicked.connect(lambda: self._start_scan(deep=True))
        sl.addWidget(self._deep_btn)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("btn_danger")
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._stop_scan)
        sl.addWidget(self._stop_btn)

        sl.addStretch()

        self._scan_lbl = QLabel("")
        self._scan_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.35);font-size:11px;")
        sl.addWidget(self._scan_lbl)
        self._scan_bar_prog = QProgressBar()
        self._scan_bar_prog.setFixedSize(120, 3)
        self._scan_bar_prog.setTextVisible(False)
        self._scan_bar_prog.setVisible(False)
        sl.addWidget(self._scan_bar_prog)
        v.addWidget(scan_bar)

        # ── Suggestion bar (hidden) ───────────────────────────────────
        self._sug_bar = QFrame()
        self._sug_bar.setStyleSheet(
            "QFrame{background:rgba(0,164,220,0.12);"
            "border-bottom:1px solid rgba(0,164,220,0.3);}")
        sb = QHBoxLayout(self._sug_bar)
        sb.setContentsMargins(14, 8, 14, 8)
        self._sug_lbl = QLabel("")
        self._sug_lbl.setStyleSheet(
            "color:rgba(0,164,220,0.9);font-size:11px;")
        sb.addWidget(self._sug_lbl)
        sb.addStretch()
        dismiss = QPushButton("✕")
        dismiss.setFixedWidth(28)
        dismiss.clicked.connect(lambda: self._sug_bar.setVisible(False))
        sb.addWidget(dismiss)
        self._sug_bar.setVisible(False)
        v.addWidget(self._sug_bar)

        # ── Main splitter ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:rgba(255,255,255,0.07);width:1px;}")

        # Left: item list
        left = QWidget()
        left.setStyleSheet("background:#131313;")
        left.setMinimumWidth(220)
        left.setMaximumWidth(300)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        self._item_list = QListWidget()
        self._item_list.setStyleSheet(
            "QListWidget{background:transparent;border:none;outline:none;}"
            "QListWidget::item{padding:7px 12px;border-radius:0;}"
            "QListWidget::item:selected{background:rgba(0,164,220,0.15);"
            "border-right:2px solid #00a4dc;}"
            "QListWidget::item:hover{background:rgba(255,255,255,0.04);}")
        self._item_list.currentRowChanged.connect(self._on_item_selected)
        lv.addWidget(self._item_list, 1)
        splitter.addWidget(left)

        # Right: item detail + candidates
        right = QWidget()
        right.setStyleSheet("background:#171717;")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(20, 20, 20, 16)
        rv.setSpacing(12)

        self._item_title = QLabel(f"Select a {self._panel_title.lower()} item")
        self._item_title.setStyleSheet(
            "font-size:14px;font-weight:500;color:#fff;")
        self._item_title.setWordWrap(True)
        rv.addWidget(self._item_title)
        self._item_sub = QLabel("")
        self._item_sub.setStyleSheet(
            "font-size:11px;color:rgba(255,255,255,0.35);font-family:monospace;")
        self._item_sub.setWordWrap(True)
        rv.addWidget(self._item_sub)

        self._loading_lbl = QLabel("Fetching candidates…")
        self._loading_lbl.setStyleSheet("color:#00a4dc;font-size:11px;")
        self._loading_lbl.setVisible(False)
        rv.addWidget(self._loading_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(218)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}")
        self._cards_wrap = QWidget()
        self._cards_wrap.setStyleSheet("background:transparent;")
        self._cards_layout = QHBoxLayout(self._cards_wrap)
        self._cards_layout.setContentsMargins(0, 4, 0, 4)
        self._cards_layout.setSpacing(10)
        self._cards_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._cards_wrap)
        rv.addStretch()
        rv.addWidget(scroll)

        actions = QHBoxLayout()
        self._skip_btn = QPushButton("Skip")
        self._skip_btn.clicked.connect(self._skip_item)
        actions.addWidget(self._skip_btn)
        self._manual_btn = QPushButton("Enter manually")
        self._manual_btn.clicked.connect(self._manual_entry)
        actions.addWidget(self._manual_btn)
        actions.addStretch()
        self._confirm_btn = QPushButton("Confirm →")
        self._confirm_btn.setObjectName("btn_accent")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm_current)
        actions.addWidget(self._confirm_btn)
        rv.addLayout(actions)
        splitter.addWidget(right)

        splitter.setSizes([240, 700])
        v.addWidget(splitter, 1)

    # ── Scan ──────────────────────────────────────────────────────────
    def _categories_for_panel(self) -> list[dict]:
        return [c for c in self._db.get_categories()
                if c["media_type"] in self._media_types]

    def _start_scan(self, deep: bool = False) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            return
        cats = self._categories_for_panel()
        sfs  = self._db.get_source_folders()
        self._db.clear_scan_items_for_media_types(self._media_types)
        self._scan_bar_prog.setRange(0, 0)
        self._scan_bar_prog.setVisible(True)
        self._scan_btn.setEnabled(False)
        self._deep_btn.setEnabled(False)
        self._stop_btn.setVisible(True)
        self._sug_bar.setVisible(False)
        self._suggestions = []

        self._scan_worker = ScanWorker(self._db, sfs, cats, deep=deep)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.item_found.connect(lambda _: None)
        self._scan_worker.suggestions.connect(self._on_suggestions)
        self._scan_worker.complete.connect(self._on_scan_complete)
        self._scan_worker.error.connect(
            lambda e: self._scan_lbl.setText(f"Error: {e}"))
        self._scan_worker.start()

    def _stop_scan(self) -> None:
        if self._scan_worker:
            self._scan_worker.stop()
        self._stop_btn.setVisible(False)
        self._scan_lbl.setText("Stopping…")

    def _on_scan_progress(self, msg: str) -> None:
        self._scan_lbl.setText(msg)

    def _on_suggestions(self, sug: list) -> None:
        existing = {c["name"].lower() for c in self._db.get_categories()}
        self._suggestions.extend(
            s for s in sug if s["name"].lower() not in existing)

    def _on_scan_complete(self, total: int) -> None:
        self._scan_bar_prog.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._deep_btn.setEnabled(True)
        self._stop_btn.setVisible(False)
        self._scan_lbl.setText(f"{total} item(s) found")
        self._db.add_log("scan", self._panel_title, f"{total} items", "ok")
        if self._suggestions:
            n = len(self._suggestions)
            self._sug_lbl.setText(
                f"{n} new categor{'y' if n == 1 else 'ies'} detected")
            self._sug_bar.setVisible(True)
        self.refresh()
        self.scan_complete.emit()

    # ── Data ──────────────────────────────────────────────────────────
    def refresh(self) -> None:
        self._items = self._db.get_scan_items_for_media_types(self._media_types)
        self._populate_list()
        self._update_toolbar()

    def _populate_list(self) -> None:
        self._item_list.clear()
        resolved = self._db.get_all_rename_choices()
        resolved_names = {r["original_name"] for r in resolved}

        pending, done = [], []
        for item in self._items:
            if item["status"] == "moved" or item["name"] in resolved_names:
                done.append(item)
            else:
                pending.append(item)

        def _section(label: str) -> None:
            li = QListWidgetItem(f"  {label}")
            li.setFlags(Qt.ItemFlag.NoItemFlags)
            li.setForeground(QColor(255, 255, 255, 51))
            font = li.font()
            font.setPointSize(9)
            li.setFont(font)
            self._item_list.addItem(li)

        if pending:
            _section(f"NEEDS REVIEW · {len(pending)}")
            for it in pending:
                li = QListWidgetItem(f"  {it['name']}")
                li.setData(Qt.ItemDataRole.UserRole, it)
                li.setForeground(QColor("#ffffff"))
                self._item_list.addItem(li)
        if done:
            _section(f"RESOLVED · {len(done)}")
            for it in done:
                li = QListWidgetItem(f"  {it['name']}")
                li.setData(Qt.ItemDataRole.UserRole, it)
                li.setForeground(QColor("#28c840"))
                self._item_list.addItem(li)

    def _update_toolbar(self) -> None:
        total    = len(self._items)
        resolved = len([i for i in self._items
                        if self._db.get_rename_choice(i["name"])
                        or i["status"] == "moved"])
        self._prog_bar.setMaximum(max(total, 1))
        self._prog_bar.setValue(resolved)
        self._prog_lbl.setText(f"{resolved} of {total} resolved")

    # ── Item selection + candidates ────────────────────────────────────
    def _on_item_selected(self, row: int) -> None:
        li = self._item_list.item(row)
        if not li:
            return
        item = li.data(Qt.ItemDataRole.UserRole)
        if not item:
            return
        self._current = item
        self._selected_candidate: Candidate | None = None
        self._confirm_btn.setEnabled(False)
        self._item_title.setText(item["name"])
        self._item_sub.setText(item["path"])
        self._clear_cards()

        saved = self._db.get_rename_choice(item["name"])
        if saved:
            self._item_title.setText(
                f"{item['name']}  →  {saved['chosen_name']}")
            return

        cat = self._db.get_category(item["detected_category"])
        if not cat:
            self._load_candidates_empty()
            return

        if self._renamer is None:
            self._refresh_renamer()

        self._loading_lbl.setVisible(True)
        self._api_worker = ApiWorker(
            self._renamer, item["name"],
            cat["media_type"], cat["api_pref"])
        self._api_worker.candidates_ready.connect(self._on_candidates)
        self._api_worker.error.connect(
            lambda e: self._loading_lbl.setText(f"Error: {e}"))
        self._api_worker.start()

    def _on_candidates(self, candidates: list) -> None:
        self._loading_lbl.setVisible(False)
        if not candidates:
            self._load_candidates_empty()
            return
        cat = self._db.get_category(
            self._current["detected_category"] if self._current else "")
        mtype     = cat["media_type"] if cat else self._media_types[0]
        with_year = mtype in ("movie", "anime_film")

        if len(candidates) == 1:
            name = sanitize_windows_name(candidates[0].display(with_year))
            self._db.set_rename_choice(
                self._current["name"], name, mtype, "auto")
            self._item_title.setText(
                f"{self._current['name']}  →  {name}  (auto)")
            self._populate_list()
            self._update_toolbar()
            return

        for c in candidates:
            card = CandidateCard(c, with_year)
            card.selected.connect(self._on_card_selected)
            self._cards_layout.addWidget(card)
            self._cards.append(card)

    def _load_candidates_empty(self) -> None:
        lbl = QLabel("No API results. Use 'Enter manually' or 'Skip'.")
        lbl.setStyleSheet("color:rgba(255,255,255,0.3);font-size:12px;")
        self._cards_layout.addWidget(lbl)

    def _on_card_selected(self, candidate: Candidate) -> None:
        self._selected_candidate = candidate
        for card in self._cards:
            card.highlight(False)
        self.sender().highlight(True)
        self._confirm_btn.setEnabled(True)

    def _clear_cards(self) -> None:
        self._cards = []
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _confirm_current(self) -> None:
        if not self._current or not self._selected_candidate:
            return
        cat = self._db.get_category(self._current["detected_category"])
        mtype     = cat["media_type"] if cat else self._media_types[0]
        with_year = mtype in ("movie", "anime_film")
        name = sanitize_windows_name(
            self._selected_candidate.display(with_year))
        self._db.set_rename_choice(self._current["name"], name, mtype, "user")
        self._populate_list()
        self._update_toolbar()
        row = self._item_list.currentRow()
        if row + 1 < self._item_list.count():
            self._item_list.setCurrentRow(row + 1)

    def _skip_item(self) -> None:
        if not self._current:
            return
        self._db.add_log("skip", self._current["path"],
                         "user skipped rename", "warning")
        row = self._item_list.currentRow()
        if row + 1 < self._item_list.count():
            self._item_list.setCurrentRow(row + 1)

    def _manual_entry(self) -> None:
        if not self._current:
            return
        text, ok = QInputDialog.getText(
            self, "Manual rename", "Enter the correct folder name:")
        if ok and text.strip():
            name  = sanitize_windows_name(text.strip())
            cat   = self._db.get_category(self._current["detected_category"])
            mtype = cat["media_type"] if cat else self._media_types[0]
            self._db.set_rename_choice(
                self._current["name"], name, mtype, "user")
            self._populate_list()
            self._update_toolbar()

    # ── Batch auto-approve ────────────────────────────────────────────
    def _approve_all_auto(self) -> None:
        if self._batch_worker and self._batch_worker.isRunning():
            return
        undecided = [it for it in self._items
                     if not self._db.get_rename_choice(it["name"])]
        if not undecided:
            self._prog_lbl.setText("All items already resolved.")
            return
        cats = self._db.get_categories()
        self._batch_worker = BatchApproveWorker(
            self._db, self._config, undecided, cats)
        self._batch_worker.progress.connect(self._on_approve_progress)
        self._batch_worker.item_approved.connect(lambda *_: None)
        self._batch_worker.complete.connect(self._on_approve_done)
        self._approve_btn.setEnabled(False)
        self._move_btn.setEnabled(False)
        self._batch_worker.start()

    def _on_approve_progress(self, current: int, total: int,
                              name: str) -> None:
        self._prog_bar.setMaximum(total)
        self._prog_bar.setValue(current)
        self._prog_lbl.setText(f"Auto-approving {current}/{total}: {name}")

    def _on_approve_done(self, approved: int) -> None:
        self._approve_btn.setEnabled(True)
        self._move_btn.setEnabled(True)
        self._populate_list()
        self._update_toolbar()
        self._prog_lbl.setText(f"Auto-approved {approved} item(s).")

    # ── Move ──────────────────────────────────────────────────────────
    def _start_move(self) -> None:
        if self._move_worker and self._move_worker.isRunning():
            return
        choices = {r["original_name"]: r["chosen_name"]
                   for r in self._db.get_all_rename_choices()}
        items = [it for it in self._items
                 if it["name"] in choices
                 and it["status"] not in ("moved", "organised")]
        if not items:
            self._prog_lbl.setText("No resolved items to move.")
            return

        dry     = self._dry_run_chk.isChecked()
        inplace = self._inplace_chk.isChecked()

        if dry:
            self._show_dry_run_preview(items, choices, inplace)
            return
        if inplace:
            self._do_inplace_move(items, choices)
            return

        dsts = self._db.get_destinations()
        cats = self._db.get_categories()
        self._move_worker = MoveWorker(self._db, items, dsts, cats, choices)
        self._move_worker.progress.connect(self._on_move_progress)
        self._move_worker.item_done.connect(lambda *_: None)
        self._move_worker.complete.connect(self._on_move_done)
        self._move_btn.setEnabled(False)
        self._approve_btn.setEnabled(False)
        self._prog_bar.setMaximum(len(items))
        self._prog_bar.setValue(0)
        self._move_worker.start()

    def _show_dry_run_preview(self, items: list[dict],
                              choices: dict, inplace: bool) -> None:
        from pathlib import Path
        from core.mover import Mover
        mover    = Mover(self._db)
        dsts     = self._db.get_destinations()
        cats     = self._db.get_categories()
        previews: list[tuple[str, str]] = []
        for it in items:
            src      = Path(it["path"])
            new_name = choices.get(it["name"], it["name"])
            if inplace:
                dst_dir = src.parent
            else:
                dst_dir = mover.compute_destination(
                    it["path"], it["detected_category"], dsts, cats)
                if dst_dir is None:
                    continue
            s, d = mover.preview_move(src, dst_dir, new_name)
            previews.append((s, d))
        dlg = _DryRunDialog(previews, self)
        dlg.exec()

    def _do_inplace_move(self, items: list[dict],
                         choices: dict) -> None:
        from pathlib import Path
        from core.mover import Mover
        mover = Mover(self._db)
        moved = errors = 0
        for it in items:
            src      = Path(it["path"])
            new_name = sanitize_windows_name(
                choices.get(it["name"], it["name"]))
            ok = mover.move(src, src.parent, new_name)
            if ok:
                self._db.update_scan_item_status(it["id"], "moved")
                moved += 1
            else:
                errors += 1
        parts = [f"{moved} moved"]
        if errors:
            parts.append(f"{errors} failed")
        self._prog_lbl.setText(", ".join(parts))
        self.refresh()

    def _on_move_progress(self, current: int, total: int, _path: str) -> None:
        self._prog_bar.setMaximum(total)
        self._prog_bar.setValue(current)
        self._prog_lbl.setText(f"Moving {current}/{total}…")

    def _on_move_done(self, moved: int, failed: int) -> None:
        self._move_btn.setEnabled(True)
        self._approve_btn.setEnabled(True)
        self._prog_bar.setValue(self._prog_bar.maximum())
        parts = [f"{moved} moved"]
        if failed:
            parts.append(f"{failed} failed")
        self._prog_lbl.setText(", ".join(parts))
        self.refresh()

    # ── Helpers ───────────────────────────────────────────────────────
    def _refresh_renamer(self) -> None:
        anidb_name    = self._config.get_api_key("anidb_client")
        anidb         = AniDBClient(anidb_name) if anidb_name else None
        self._renamer = Renamer(
            self._db,
            TMDbClient(self._config.get_api_key("tmdb")),
            AniListClient(),
            anidb,
        )

    def on_shown(self) -> None:
        self._refresh_renamer()
        self.refresh()


class _DryRunDialog(QDialog):
    def __init__(self, previews: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dry run — planned operations")
        self.setMinimumSize(900, 420)
        v = QVBoxLayout(self)
        lbl = QLabel(f"{len(previews)} folder(s) would be moved/renamed:")
        lbl.setStyleSheet("color:rgba(255,255,255,0.5);font-size:12px;")
        v.addWidget(lbl)
        tbl = QTableWidget(len(previews), 2)
        tbl.setHorizontalHeaderLabels(["Source", "Destination"])
        tbl.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, (src, dst) in enumerate(previews):
            tbl.setItem(r, 0, QTableWidgetItem(src))
            tbl.setItem(r, 1, QTableWidgetItem(dst))
        v.addWidget(tbl, 1)
        ok = QPushButton("Close")
        ok.clicked.connect(self.accept)
        v.addWidget(ok)
