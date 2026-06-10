"""QThread that moves items and emits progress signals."""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from core.mover import Mover
from core.database import Database
from core.nfo_writer import write_video_sidecars
from core.utils import sanitize_windows_name


class MoveWorker(QThread):
    progress   = pyqtSignal(int, int, str)  # current, total, path
    item_done  = pyqtSignal(str, bool)      # path, success
    complete   = pyqtSignal(int, int)       # moved, failed
    error      = pyqtSignal(str)

    def __init__(self, db: Database,
                 items: list[dict],
                 destinations: list[dict],
                 categories: list[dict],
                 rename_map: dict[str, str],
                 meta_map: dict[str, dict] | None = None,
                 write_nfo: bool = False) -> None:
        """
        items       : list of scan_item dicts with 'path', 'detected_category'
        rename_map  : {original_name: chosen_name} from DB choices
        meta_map    : {original_name: candidate meta} for NFO/artwork sidecars
        write_nfo   : write movie.nfo/tvshow.nfo + poster.jpg after each move
        """
        super().__init__()
        self._db           = db
        self._items        = items
        self._destinations = destinations
        self._categories   = categories
        self._rename_map   = rename_map
        self._meta_map     = meta_map or {}
        self._write_nfo    = write_nfo
        self._abort        = False

    def stop(self) -> None:
        self._abort = True

    def run(self) -> None:
        mover     = Mover(self._db)
        moved     = 0
        failed    = 0
        total     = len(self._items)
        cat_types = {c["name"]: c["media_type"] for c in self._categories}

        for idx, item in enumerate(self._items):
            if self._abort:
                break

            src      = Path(item["path"])
            category = item["detected_category"]
            new_name = self._rename_map.get(src.name) or src.name

            self.progress.emit(idx + 1, total, str(src))

            dst_dir = mover.compute_destination(
                str(src), category, self._destinations, self._categories)

            if dst_dir is None:
                self._db.add_log("move", str(src), "No destination configured", "error")
                failed += 1
                self.item_done.emit(str(src), False)
                continue

            ok = mover.move(src, dst_dir, new_name)
            if ok:
                moved += 1
                self._db.update_scan_item_status(item["id"], "moved")
                self._write_sidecars(src.name, dst_dir, new_name,
                                     cat_types.get(category, "movie"))
            else:
                failed += 1
                self._db.update_scan_item_status(item["id"], "error")
            self.item_done.emit(str(src), ok)

        self.complete.emit(moved, failed)

    def _write_sidecars(self, original_name: str, dst_dir: Path,
                        new_name: str, media_type: str) -> None:
        if not self._write_nfo:
            return
        meta = self._meta_map.get(original_name)
        if not meta:
            return
        dst = dst_dir / sanitize_windows_name(new_name)
        try:
            if write_video_sidecars(dst, media_type, meta):
                self._db.add_log("sidecar", str(dst),
                                 "NFO + artwork written", "ok")
        except Exception as exc:
            self._db.add_log("sidecar", str(dst), str(exc), "error")
