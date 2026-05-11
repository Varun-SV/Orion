"""
Open Library API client — book search and metadata, free, no key required.
Docs: https://openlibrary.org/developers/api

Endpoints used:
  /search.json?q=<query>   — full-text search
  /works/<olid>.json       — work detail (series info lives in subjects)
"""
from __future__ import annotations
import logging
import requests

log = logging.getLogger(__name__)

_OL_BASE = "https://openlibrary.org"


class BookCandidate:
    __slots__ = ("title", "author", "series", "series_index",
                 "year", "isbn", "ol_key", "score")

    def __init__(self, title: str, author: str,
                 series: str = "", series_index: str = "",
                 year: str = "", isbn: str = "",
                 ol_key: str = "", score: float = 0.0) -> None:
        self.title        = title
        self.author       = author
        self.series       = series
        self.series_index = series_index
        self.year         = year
        self.isbn         = isbn
        self.ol_key       = ol_key
        self.score        = score

    def dest_path(self, ext: str) -> tuple[str, str, str]:
        """
        Returns (author_dir, series_dir, filename) for:
          Author/Series/Title.ext  or  Author/Title.ext when no series.
        """
        series_dir = self.series if self.series else ""
        filename   = f"{self.title}{ext}"
        return self.author, series_dir, filename


class OpenLibraryClient:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "Orion/1.0 (https://github.com/Varun-SV/Orion)"

    def search_books(self, title: str,
                     author: str = "") -> list[BookCandidate]:
        """Search Open Library. Returns up to 8 candidates."""
        q = title
        if author:
            q = f"{title} {author}"
        try:
            r = self._session.get(f"{_OL_BASE}/search.json",
                                  params={"q": q, "limit": 8,
                                          "fields": "key,title,author_name,"
                                                    "first_publish_year,isbn,"
                                                    "subject,edition_count"},
                                  timeout=12)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            log.warning("OpenLibrary search failed: %s", exc)
            return []

        out: list[BookCandidate] = []
        for doc in data.get("docs", []):
            auth   = doc.get("author_name", ["Unknown"])
            auth   = auth[0] if auth else "Unknown"
            year   = str(doc.get("first_publish_year", "")) or ""
            isbn   = (doc.get("isbn") or [""])[0]
            ol_key = doc.get("key", "")
            # Detect series from subject tags like "Dune Chronicles"
            series, series_idx = self._extract_series(doc.get("subject", []))
            out.append(BookCandidate(
                title        = doc.get("title", ""),
                author       = auth,
                series       = series,
                series_index = series_idx,
                year         = year,
                isbn         = isbn,
                ol_key       = ol_key,
            ))
        return out

    @staticmethod
    def _extract_series(subjects: list[str]) -> tuple[str, str]:
        """Heuristic: find subjects that look like series names."""
        for subj in subjects:
            low = subj.lower()
            for kw in (" series", " chronicles", " saga", " trilogy", " cycle"):
                if kw in low:
                    return subj, ""
        return "", ""
