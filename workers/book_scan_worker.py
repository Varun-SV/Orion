"""
Book scan worker — walks source folders for epub/pdf files, reads embedded
metadata (ebooklib for epub, pypdf for pdf), falls back to Open Library
text search when metadata is sparse.

Emits:
  progress(current, total, filename)
  item_found(dict)
  complete(int)
  error(str)
"""
from __future__ import annotations
import os
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from core.database import Database
from api.openlibrary import OpenLibraryClient

_BOOK_EXTS = {".epub", ".pdf"}


def _read_epub_meta(path: str) -> dict:
    try:
        from ebooklib import epub, ITEM_DOCUMENT  # type: ignore
        book = epub.read_epub(path, options={"ignore_ncx": True})
        meta = book.metadata.get("http://purl.org/dc/elements/1.1/", {})

        def _first(key: str) -> str:
            vals = meta.get(key, [])
            return str(vals[0][0]) if vals else ""

        return {
            "title":  _first("title"),
            "author": _first("creator"),
            "year":   _first("date")[:4],
            "isbn":   _first("identifier"),
        }
    except Exception:
        return {}


def _read_pdf_meta(path: str) -> dict:
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(path)
        info   = reader.metadata or {}
        author = str(info.get("/Author", ""))
        title  = str(info.get("/Title", ""))
        year   = ""
        date   = str(info.get("/CreationDate", ""))
        if date and len(date) >= 5:
            year = date[2:6] if date.startswith("D:") else date[:4]
        return {"title": title, "author": author, "year": year, "isbn": ""}
    except Exception:
        return {}


def _meta_complete(meta: dict) -> bool:
    return bool(meta.get("title") and meta.get("author"))


class BookScanWorker(QThread):
    progress   = pyqtSignal(int, int, str)
    item_found = pyqtSignal(dict)
    complete   = pyqtSignal(int)
    error      = pyqtSignal(str)

    def __init__(self, db: Database,
                 source_folders: list[dict]) -> None:
        super().__init__()
        self._db      = db
        self._folders = source_folders
        self._abort   = False
        self._ol      = OpenLibraryClient()

    def stop(self) -> None:
        self._abort = True

    def run(self) -> None:
        files = self._collect_files()
        total = len(files)

        for i, fpath in enumerate(files):
            if self._abort:
                break
            self.progress.emit(i + 1, total, Path(fpath).name)
            try:
                item = self._identify(fpath)
            except Exception as exc:
                self.error.emit(f"{Path(fpath).name}: {exc}")
                continue
            if item:
                self._db.upsert_book_item(**item)
                self.item_found.emit(item)

        self.complete.emit(total)

    def _collect_files(self) -> list[str]:
        files: list[str] = []
        for sf in self._folders:
            root = Path(sf["path"])
            if not root.exists():
                continue
            for dirpath, _, filenames in os.walk(root):
                for fn in filenames:
                    if Path(fn).suffix.lower() in _BOOK_EXTS:
                        files.append(str(Path(dirpath) / fn))
        return files

    def _identify(self, fpath: str) -> dict | None:
        p      = Path(fpath)
        ext    = p.suffix.lower()
        meta: dict = {}

        if ext == ".epub":
            meta = _read_epub_meta(fpath)
        elif ext == ".pdf":
            meta = _read_pdf_meta(fpath)

        series = series_index = ol_key = ""
        status = "pending"

        if _meta_complete(meta):
            status = "identified"
            # Try OL for series info using known title/author
            candidates = self._ol.search_books(meta["title"], meta["author"])
            if candidates:
                series       = candidates[0].series
                series_index = candidates[0].series_index
                ol_key       = candidates[0].ol_key
        else:
            stem       = p.stem
            candidates = self._ol.search_books(stem)
            if candidates:
                c             = candidates[0]
                meta["title"]  = meta.get("title") or c.title
                meta["author"] = meta.get("author") or c.author
                meta["year"]   = meta.get("year") or c.year
                meta["isbn"]   = meta.get("isbn") or c.isbn
                series        = c.series
                series_index  = c.series_index
                ol_key        = c.ol_key
                status        = "identified"

        return {
            "source_path":  fpath,
            "filename":     p.name,
            "title":        meta.get("title", ""),
            "author":       meta.get("author", ""),
            "series":       series,
            "series_index": series_index,
            "year":         meta.get("year", ""),
            "isbn":         meta.get("isbn", ""),
            "ol_key":       ol_key,
            "fmt":          ext.lstrip("."),
            "status":       status,
        }
