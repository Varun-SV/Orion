"""
Music panel — scan music files, review identified metadata, approve or
correct rename choices, and organise into Jellyfin-compatible structure.

Naming convention:  Artist / Album (Year) / TrackNum - Title.ext
"""
from __future__ import annotations
import shutil
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QFrame, QCheckBox, QComboBox, QDialog,
    QFormLayout, QLineEdit, QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from core import artwork, nfo_writer, server_link
from core.config import Config
from core.database import Database
from core.mover import Mover
from core.utils import sanitize_windows_name
from api.musicbrainz import MusicBrainzClient
from workers.music_scan_worker import MusicScanWorker

_STATUS_COLORS = {
    "identified": QColor(0, 200, 100, 180),
    "approved":   QColor(0, 164, 220, 200),
    "moved":      QColor(100, 100, 100, 150),
    "pending":    QColor(255, 188, 46, 180),
}


class MusicPanel(QWidget):
    def __init__(self, db: Database, config: Config, parent=None):
        super().__init__(parent)
        self._db     = db
        self._config = config
        self._worker: MusicScanWorker | None = None
        self._mover  = Mover(db)
        self._setup_ui()

    def _setup_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Music Library")
        title.setStyleSheet("font-size:17px; font-weight:500; color:#fff;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._dry_run_chk = QCheckBox("Dry run")
        self._dry_run_chk.setToolTip("Preview destination paths without moving files")
        hdr.addWidget(self._dry_run_chk)

        self._nfo_chk = QCheckBox("Write NFO + cover art")
        self._nfo_chk.setToolTip(
            "Write artist.nfo/album.nfo and a Cover Art Archive cover.jpg "
            "into the organised folders (covers need a MusicBrainz match)")
        self._nfo_chk.setChecked(bool(self._config.get_pref("nfo_music", False)))
        self._nfo_chk.toggled.connect(
            lambda on: self._config.set_pref("nfo_music", on))
        hdr.addWidget(self._nfo_chk)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("btn_danger")
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._stop_scan)
        hdr.addWidget(self._stop_btn)

        self._scan_btn = QPushButton("Scan music")
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

        # fpcalc hint
        self._fpcalc_banner = QLabel()
        self._fpcalc_banner.setWordWrap(True)
        self._fpcalc_banner.setStyleSheet(
            "background:rgba(254,188,46,0.08);"
            "border:1px solid rgba(254,188,46,0.2);"
            "border-radius:6px; padding:6px 10px;"
            "color:#febc2e; font-size:11px;")
        self._fpcalc_banner.setVisible(False)
        v.addWidget(self._fpcalc_banner)

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
            ["File", "Artist", "Album", "Year", "Track / Title", "Status"])
        h = self._tbl.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 5):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.doubleClicked.connect(self._edit_row)
        v.addWidget(self._tbl, 1)

        # Stats bar
        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet("color:rgba(255,255,255,0.3); font-size:11px;")
        v.addWidget(self._stats_lbl)

        self._refresh_table()
        self._check_fpcalc()

    def _check_fpcalc(self) -> None:
        if not shutil.which("fpcalc"):
            self._fpcalc_banner.setText(
                "fpcalc not found — AcoustID fingerprinting is disabled. "
                "Orion will use AudD (if configured) then MusicBrainz text search as fallbacks. "
                "To enable full fingerprinting: sudo pacman -S chromaprint  "
                "or  sudo apt install libchromaprint-tools")
            self._fpcalc_banner.setVisible(True)

    def _start_scan(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._db.clear_music_items()
        self._tbl.setRowCount(0)
        self._prog_bar.setRange(0, 0)
        self._prog_bar.setVisible(True)
        self._scan_btn.setEnabled(False)
        self._stop_btn.setVisible(True)

        sfs  = self._db.get_source_folders()
        akey = self._config.get_api_key("acoustid")
        dkey = self._config.get_api_key("audd")
        self._worker = MusicScanWorker(self._db, sfs,
                                       acoustid_key=akey, audd_key=dkey)
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
        self._prog_lbl.setText(f"Scan complete — {total} audio file(s) found.")
        self._update_stats()

    def _on_error(self, msg: str) -> None:
        self._prog_lbl.setText(f"Error: {msg}")

    def _add_row(self, item: dict) -> None:
        r = self._tbl.rowCount()
        self._tbl.insertRow(r)
        track_title = (f"{item['track_number']} - " if item.get("track_number") else "") + item.get("title", "")
        cols = [
            item.get("filename", ""),
            item.get("artist", ""),
            item.get("album", ""),
            item.get("year", ""),
            track_title,
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
        for item in self._db.get_music_items():
            self._add_row(item)
        self._update_stats()

    def _update_stats(self) -> None:
        items = self._db.get_music_items()
        n = len(items)
        ident = sum(1 for i in items if i["status"] in ("identified", "approved"))
        self._stats_lbl.setText(f"{n} file(s) · {ident} identified")

    def _approve_all(self) -> None:
        for item in self._db.get_music_items():
            if item["status"] == "identified":
                self._db.set_music_rename_choice(
                    item["source_path"],
                    artist       = item["artist"],
                    album        = item["album"],
                    year         = item["year"],
                    track_number = item["track_number"],
                    title        = item["title"],
                    mbid         = item["mbid"],
                    source       = "auto",
                )
                self._db.update_music_item_status(item["source_path"], "approved")
        self._refresh_table()

    def _start_move(self) -> None:
        dry = self._dry_run_chk.isChecked()
        items = self._db.get_music_items()
        previews: list[tuple[str, str]] = []
        moved = errors = 0
        # (album_dir, album, artist, year, recording_mbid) for sidecars
        organised: dict[Path, tuple[str, str, str, str]] = {}

        for item in items:
            choice = self._db.get_music_rename_choice(item["source_path"])
            if not choice:
                continue
            src  = Path(item["source_path"])
            ext  = src.suffix
            artist  = sanitize_windows_name(choice["artist"] or "Unknown Artist")
            album   = sanitize_windows_name(
                f"{choice['album']} ({choice['year']})"
                if choice["year"] else choice["album"] or "Unknown Album"
            )
            tnum = choice["track_number"]
            try:
                num = int(tnum.split("/")[0])
                stem = f"{num:02d} - {choice['title']}"
            except (ValueError, AttributeError):
                stem = choice["title"] or src.stem
            filename = sanitize_windows_name(stem) + ext

            if dry:
                src_str, dst_str = self._mover.preview_move(
                    src, src.parent / artist / album, filename)
                previews.append((src_str, dst_str))
            else:
                ok = self._mover.move_inplace(src, [artist, album], filename)
                if ok:
                    self._db.update_music_item_status(item["source_path"], "moved")
                    moved += 1
                    album_dir = src.parent / artist / album
                    organised.setdefault(album_dir, (
                        choice["album"] or "Unknown Album",
                        choice["artist"] or "Unknown Artist",
                        choice["year"] or "",
                        choice["mbid"] or "",
                    ))
                else:
                    errors += 1

        if dry:
            self._show_dry_run(previews)
            return

        parts = [f"Done — {moved} moved, {errors} failed."]
        if moved and self._nfo_chk.isChecked() and organised:
            threading.Thread(target=self._write_sidecars,
                             args=(organised,), daemon=True).start()
            parts.append("Writing NFO + covers in background…")
        if moved and server_link.refresh_after_move(self._db, self._config):
            parts.append("Server refresh triggered.")
        self._prog_lbl.setText("  ".join(parts))
        self._refresh_table()

    def _write_sidecars(self,
                        organised: dict[Path, tuple[str, str, str, str]]) -> None:
        """Write artist.nfo / album.nfo / cover.jpg for each organised album.

        Runs on a daemon thread: cover lookups hit MusicBrainz (1 req/s
        throttle) and Cover Art Archive, which would freeze the UI."""
        mb      = MusicBrainzClient()
        written = 0
        for album_dir, (album, artist, year, mbid) in organised.items():
            nfo_writer.write_artist_nfo(album_dir.parent, artist)
            release_id = mb.get_release_id(mbid) if mbid else ""
            nfo_writer.write_album_nfo(album_dir, album, artist, year, release_id)
            if release_id:
                artwork.save_album_cover(release_id, album_dir / "cover.jpg")
            written += 1
        self._db.add_log("sidecar", f"{written} album folder(s)",
                         "music NFO + covers written", "ok")

    def _show_dry_run(self, previews: list[tuple[str, str]]) -> None:
        dlg = DryRunDialog(previews, self)
        dlg.exec()

    def _edit_row(self) -> None:
        row = self._tbl.currentRow()
        if row < 0:
            return
        path = self._tbl.item(row, 0).data(Qt.ItemDataRole.UserRole)
        items = [i for i in self._db.get_music_items()
                 if i["source_path"] == path]
        if not items:
            return
        item = items[0]
        dlg  = MusicEditDialog(item, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.result()
            self._db.set_music_rename_choice(
                item["source_path"],
                artist=d["artist"], album=d["album"], year=d["year"],
                track_number=d["track_number"], title=d["title"],
                source="user",
            )
            self._db.update_music_item_status(item["source_path"], "approved")
            self._refresh_table()

    def on_shown(self) -> None:
        self._refresh_table()


class MusicEditDialog(QDialog):
    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit music metadata")
        self.setMinimumWidth(420)
        self._item = item
        v = QVBoxLayout(self)
        form = QFormLayout()
        self._artist = QLineEdit(item.get("artist", ""))
        self._album  = QLineEdit(item.get("album", ""))
        self._year   = QLineEdit(item.get("year", ""))
        self._track  = QLineEdit(item.get("track_number", ""))
        self._title  = QLineEdit(item.get("title", ""))
        form.addRow("Artist:",       self._artist)
        form.addRow("Album:",        self._album)
        form.addRow("Year:",         self._year)
        form.addRow("Track number:", self._track)
        form.addRow("Title:",        self._title)
        v.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def result(self) -> dict:  # type: ignore[override]
        return {
            "artist":       self._artist.text().strip(),
            "album":        self._album.text().strip(),
            "year":         self._year.text().strip(),
            "track_number": self._track.text().strip(),
            "title":        self._title.text().strip(),
        }


class DryRunDialog(QDialog):
    def __init__(self, previews: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dry run — planned operations")
        self.setMinimumSize(800, 400)
        v = QVBoxLayout(self)
        lbl = QLabel(f"{len(previews)} file(s) would be moved:")
        lbl.setStyleSheet("color:rgba(255,255,255,0.5); font-size:12px;")
        v.addWidget(lbl)
        tbl = QTableWidget(len(previews), 2)
        tbl.setHorizontalHeaderLabels(["Source", "Destination"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, (src, dst) in enumerate(previews):
            tbl.setItem(r, 0, QTableWidgetItem(src))
            tbl.setItem(r, 1, QTableWidgetItem(dst))
        v.addWidget(tbl, 1)
        ok = QPushButton("Close")
        ok.clicked.connect(self.accept)
        v.addWidget(ok)
