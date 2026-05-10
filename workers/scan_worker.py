"""QThread wrapper around Scanner."""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from core.scanner import Scanner
from core.database import Database


class ScanWorker(QThread):
    progress     = pyqtSignal(str)         # status message
    item_found   = pyqtSignal(dict)        # scan result dict
    suggestions  = pyqtSignal(list)        # category suggestions (pre-scan)
    complete     = pyqtSignal(int)         # total items found
    error        = pyqtSignal(str)

    def __init__(self, db: Database,
                 source_folders: list[dict],
                 categories: list[dict],
                 pre_scan_only: bool = False,
                 deep: bool = False) -> None:
        super().__init__()
        self._db             = db
        self._source_folders = source_folders
        self._categories     = categories
        self._pre_scan_only  = pre_scan_only
        self._deep           = deep
        self._abort          = False

    def stop(self) -> None:
        self._abort = True

    def run(self) -> None:
        scanner = Scanner(self._db)
        total   = 0

        for sf in self._source_folders:
            if self._abort:
                break
            root = Path(sf["path"])
            if not root.exists():
                self.error.emit(f"Source folder not found: {root}")
                continue

            if self._pre_scan_only:
                sug = scanner.detect_categories_from_scan(root)
                self.suggestions.emit(sug)
                continue

            # Emit category suggestions before item scan so the UI can buffer them
            if self._deep:
                self.progress.emit(f"Deep-scanning categories in {root.name}…")
                sug = scanner.deep_scan_categories(
                    root, progress_cb=lambda msg: self.progress.emit(msg))
            else:
                sug = scanner.detect_categories_from_scan(root)
            if sug:
                self.suggestions.emit(sug)

            self.progress.emit(f"Scanning {root} …")
            results = scanner.scan(
                sf["id"], root, self._categories,
                progress_cb=lambda msg: self.progress.emit(msg),
                deep=self._deep,
            )
            for r in results:
                if self._abort:
                    break
                self.item_found.emit({
                    "path":     r.path,
                    "name":     r.name,
                    "category": r.category,
                    "is_leaf":  r.is_leaf,
                })
                total += 1

        self.complete.emit(total)
