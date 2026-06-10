"""
Books panel — scan epub/pdf files, review Open Library metadata,
approve or correct rename choices, and organise into:
  Author / Series / Title.ext

Double-click a row to edit metadata manually.
"""
from __future__ import annotations
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QCheckBox, QDialog, QFormLayout,
    QLineEdit, QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from core import artwork, server_link
from core.config import Config
from core.database import Database
from core.mover import Mover
from core.utils import sanitize_windows_name
from workers.book_scan_worker import BookScanWorker

_STATUS_COLORS = {
    "identified": QColor(0, 200, 100, 180),
    "approved":   QColor(0, 164, 220, 200),
    "moved":      QColor(100, 100, 100, 150),
    "pending":    QColor(255, 188, 46, 180),
}


class BooksPanel(QWidget):
    def __init__(self, db: Database, config: Config, parent=None):
        super().__init__(parent)
        self._db     = db
        self._config = config
        self._worker: BookScanWorker | None = None
        self._mover  = Mover(db)
        self._setup_ui()

    def _setup_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Books Library")
        title.setStyleSheet("font-size:17px; font-weight:500; color:#fff;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._dry_run_chk = QCheckBox("Dry run")
        self._dry_run_chk.setToolTip("Preview destination paths without moving files")
        hdr.addWidget(self._dry_run_chk)

        self._cover_chk = QCheckBox("Save cover art")
        self._cover_chk.setToolTip(
            "Download the Open Library cover (by ISBN) as '<Title>.jpg' "
            "next to each organised book")
        self._cover_chk.setChecked(bool(self._config.get_pref("nfo_books", False)))
        self._cover_chk.toggled.connect(
            lambda on: self._config.set_pref("nfo_books", on))
        hdr.addWidget(self._cover_chk)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("btn_danger")
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._stop_scan)
        hdr.addWidget(self._stop_btn)

        self._scan_btn = QPushButton("Scan books")
        self._scan_btn.setObjectName("btn_accent")
        self._scan_btn.clicked.connect(self._start_scan)
        hdr.addWidget(self._scan_btn)

        self._approve_btn = QPushButton("Approve all identified")
        self._approve_btn.clicked.connect(self._approve_all)
        hdr.addWidget(self._approve_btn)

        self._move_btn = QPushButton("Organise →")
        self._move_btn.clicked.connect(self._start_move)
        hdr.addWidget(self._move_btn)

        v.addLayout(hdr)

        # Progress
        self._prog_lbl = QLabel("")
        self._prog_lbl.setStyleSheet("color:rgba(255,255,255,0.4); font-size:11px;")
        v.addWidget(self._prog_lbl)
        self._prog_bar = QProgressBar()
        self._prog_bar.setFixedHeight(4)
        self._prog_bar.setVisible(False)
        v.addWidget(self._prog_bar)

        # Table
        self._tbl = QTableWidget(0, 6)
        self._tbl.setHorizontalHeaderLabels(
            ["File", "Author", "Series", "Title", "Year", "Status"])
        h = self._tbl.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 4, 5):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.doubleClicked.connect(self._edit_row)
        v.addWidget(self._tbl, 1)

        # Stats
        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet("color:rgba(255,255,255,0.3); font-size:11px;")
        v.addWidget(self._stats_lbl)

        self._refresh_table()

    def _start_scan(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._db.clear_book_items()
        self._tbl.setRowCount(0)
        self._prog_bar.setRange(0, 0)
        self._prog_bar.setVisible(True)
        self._scan_btn.setEnabled(False)
        self._stop_btn.setVisible(True)

        sfs = self._db.get_source_folders()
        self._worker = BookScanWorker(self._db, sfs)
        self._worker.progress.connect(self._on_progress)
        self._worker.item_found.connect(self._on_item_found)
        self._worker.complete.connect(self._on_complete)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop_scan(self) -> None:
        if self._worker:
            self._worker.stop()
        self._stop_btn.setVisible(False)

    def _on_progress(self, cur: int, total: int, name: str) -> None:
        self._prog_bar.setRange(0, total)
        self._prog_bar.setValue(cur)
        self._prog_lbl.setText(f"Scanning {cur}/{total}: {name}")

    def _on_item_found(self, item: dict) -> None:
        self._add_row(item)
        self._update_stats()

    def _on_complete(self, total: int) -> None:
        self._prog_bar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._stop_btn.setVisible(False)
        self._prog_lbl.setText(f"Scan complete — {total} book(s) found.")
        self._update_stats()

    def _on_error(self, msg: str) -> None:
        self._prog_lbl.setText(f"Error: {msg}")

    def _add_row(self, item: dict) -> None:
        r = self._tbl.rowCount()
        self._tbl.insertRow(r)
        cols = [
            item.get("filename", ""),
            item.get("author", ""),
            item.get("series", ""),
            item.get("title", ""),
            item.get("year", ""),
            item.get("status", "pending"),
        ]
        for c, text in enumerate(cols):
            cell = QTableWidgetItem(text)
            cell.setData(Qt.ItemDataRole.UserRole, item["source_path"])
            self._tbl.setItem(r, c, cell)
        color = _STATUS_COLORS.get(item.get("status", ""), QColor(180, 180, 180, 120))
        self._tbl.item(r, 5).setForeground(color)

    def _refresh_table(self) -> None:
        self._tbl.setRowCount(0)
        for item in self._db.get_book_items():
            self._add_row(item)
        self._update_stats()

    def _update_stats(self) -> None:
        items = self._db.get_book_items()
        n = len(items)
        ident = sum(1 for i in items if i["status"] in ("identified", "approved"))
        self._stats_lbl.setText(f"{n} book(s) · {ident} identified")

    def _approve_all(self) -> None:
        for item in self._db.get_book_items():
            if item["status"] == "identified":
                self._db.set_book_rename_choice(
                    item["source_path"],
                    title        = item["title"],
                    author       = item["author"],
                    series       = item["series"],
                    series_index = item["series_index"],
                    year         = item["year"],
                    source       = "auto",
                )
                self._db.update_book_item_status(item["source_path"], "approved")
        self._refresh_table()

    def _start_move(self) -> None:
        dry = self._dry_run_chk.isChecked()
        items = self._db.get_book_items()
        previews: list[tuple[str, str]] = []
        moved = errors = 0
        covers: list[tuple[str, Path]] = []   # (isbn, dest jpg path)

        for item in items:
            choice = self._db.get_book_rename_choice(item["source_path"])
            if not choice:
                continue
            src    = Path(item["source_path"])
            ext    = src.suffix
            author = sanitize_windows_name(choice["author"] or "Unknown Author")
            series = sanitize_windows_name(choice["series"]) if choice["series"] else ""
            fname  = sanitize_windows_name(choice["title"] or src.stem) + ext
            parts  = [author, series] if series else [author]

            if dry:
                dst_dir = src.parent.joinpath(*parts)
                src_str, dst_str = self._mover.preview_move(src, dst_dir, fname)
                previews.append((src_str, dst_str))
            else:
                ok = self._mover.move_inplace(src, parts, fname)
                if ok:
                    self._db.update_book_item_status(item["source_path"], "moved")
                    moved += 1
                    if item.get("isbn"):
                        dst_dir = src.parent.joinpath(*parts)
                        covers.append(
                            (item["isbn"], dst_dir / (Path(fname).stem + ".jpg")))
                else:
                    errors += 1

        if dry:
            self._show_dry_run(previews)
            return

        status = [f"Done — {moved} moved, {errors} failed."]
        if moved and self._cover_chk.isChecked() and covers:
            threading.Thread(target=self._download_covers,
                             args=(covers,), daemon=True).start()
            status.append("Downloading covers in background…")
        if moved and server_link.refresh_after_move(self._db, self._config):
            status.append("Server refresh triggered.")
        self._prog_lbl.setText("  ".join(status))
        self._refresh_table()

    def _download_covers(self, covers: list[tuple[str, Path]]) -> None:
        done = sum(1 for isbn, dest in covers
                   if artwork.save_book_cover(isbn, dest))
        self._db.add_log("sidecar", f"{done}/{len(covers)} book cover(s)",
                         "Open Library covers downloaded", "ok")

    def _show_dry_run(self, previews: list[tuple[str, str]]) -> None:
        from ui.music_panel import DryRunDialog
        dlg = DryRunDialog(previews, self)
        dlg.exec()

    def _edit_row(self) -> None:
        row = self._tbl.currentRow()
        if row < 0:
            return
        path  = self._tbl.item(row, 0).data(Qt.ItemDataRole.UserRole)
        items = [i for i in self._db.get_book_items()
                 if i["source_path"] == path]
        if not items:
            return
        item = items[0]
        dlg  = BookEditDialog(item, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.result()
            self._db.set_book_rename_choice(
                item["source_path"],
                title=d["title"], author=d["author"],
                series=d["series"], series_index=d["series_index"],
                year=d["year"], source="user",
            )
            self._db.update_book_item_status(item["source_path"], "approved")
            self._refresh_table()

    def on_shown(self) -> None:
        self._refresh_table()


class BookEditDialog(QDialog):
    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit book metadata")
        self.setMinimumWidth(420)
        v = QVBoxLayout(self)
        form = QFormLayout()
        self._title   = QLineEdit(item.get("title", ""))
        self._author  = QLineEdit(item.get("author", ""))
        self._series  = QLineEdit(item.get("series", ""))
        self._idx     = QLineEdit(item.get("series_index", ""))
        self._year    = QLineEdit(item.get("year", ""))
        form.addRow("Title:",         self._title)
        form.addRow("Author:",        self._author)
        form.addRow("Series:",        self._series)
        form.addRow("Series index:",  self._idx)
        form.addRow("Year:",          self._year)
        v.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def result(self) -> dict:  # type: ignore[override]
        return {
            "title":        self._title.text().strip(),
            "author":       self._author.text().strip(),
            "series":       self._series.text().strip(),
            "series_index": self._idx.text().strip(),
            "year":         self._year.text().strip(),
        }
