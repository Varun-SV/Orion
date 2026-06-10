"""
Rate-limit-aware batch auto-approval worker.

Fires parallel API requests up to the safe batch limit for the APIs
in use, then falls back to sequential for the remaining items so we
don't exceed rate limits.

  TMDb   : ~40 req / 10 s → safe parallel batch: 20
  AniList: ~90 req / min  → safe parallel batch: 15
  AniDB  : 1 req / 2 s, throttled inside AniDBClient via a class-level
           lock — parallel workers still respect the limit, batch: 5
  mixed  : uses the most conservative limit
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal
from core.database import Database
from core.config import Config
from core.renamer import Renamer
from core.utils import sanitize_windows_name
from api.tmdb import TMDbClient
from api.anilist import AniListClient
from api.anidb import AniDBClient


_BATCH_LIMITS: dict[str, int] = {
    "tmdb":    20,
    "anilist": 15,
    "anidb":    5,
    "both":    10,
}


class BatchApproveWorker(QThread):
    progress      = pyqtSignal(int, int, str)   # current, total, item_name
    item_approved = pyqtSignal(str, str, str)   # original_name, chosen_name, media_type
    complete      = pyqtSignal(int)             # total approved
    error         = pyqtSignal(str)

    def __init__(self, db: Database, config: Config,
                 items: list[dict], categories: list[dict]) -> None:
        super().__init__()
        self._db           = db
        self._tmdb_key     = config.get_api_key("tmdb")
        self._anidb_client = config.get_api_key("anidb_client")
        self._items        = items
        self._cat_map      = {c["name"]: c for c in categories}
        self._abort        = False

    def stop(self) -> None:
        self._abort = True

    def run(self) -> None:
        total      = len(self._items)
        approved   = 0
        current    = 0

        batch_size = self._safe_batch_size()
        parallel   = self._items[:batch_size]
        sequential = self._items[batch_size:]

        # ── Parallel phase ────────────────────────────────────────────
        if parallel and not self._abort:
            with ThreadPoolExecutor(max_workers=min(batch_size, 8)) as pool:
                futures = {
                    pool.submit(self._fetch, item): item
                    for item in parallel
                }
                for fut in as_completed(futures):
                    if self._abort:
                        break
                    item = futures[fut]
                    current += 1
                    try:
                        result = fut.result()
                    except Exception as exc:
                        self.error.emit(str(exc))
                        result = None
                    if result:
                        orig, chosen, mtype, meta = result
                        self._db.set_rename_choice(orig, chosen, mtype,
                                                   "auto", meta)
                        self.item_approved.emit(orig, chosen, mtype)
                        approved += 1
                    self.progress.emit(current, total, item["name"])

        # ── Sequential phase ──────────────────────────────────────────
        anidb_seq   = AniDBClient(self._anidb_client) if self._anidb_client else None
        seq_renamer = Renamer(
            self._db,
            TMDbClient(self._tmdb_key),
            AniListClient(),
            anidb_seq,
        )
        for item in sequential:
            if self._abort:
                break
            current += 1
            try:
                result = self._fetch_with(seq_renamer, item)
            except Exception:
                result = None
            if result:
                orig, chosen, mtype, meta = result
                self._db.set_rename_choice(orig, chosen, mtype, "auto", meta)
                self.item_approved.emit(orig, chosen, mtype)
                approved += 1
            self.progress.emit(current, total, item["name"])

        self.complete.emit(approved)

    # ── Helpers ───────────────────────────────────────────────────────

    def _fetch(self, item: dict) -> tuple[str, str, str, dict] | None:
        """Create per-thread clients (requests.Session is not thread-safe to share)."""
        anidb   = AniDBClient(self._anidb_client) if self._anidb_client else None
        renamer = Renamer(
            self._db,
            TMDbClient(self._tmdb_key),
            AniListClient(),
            anidb,
        )
        return self._fetch_with(renamer, item)

    def _fetch_with(self, renamer: Renamer,
                    item: dict) -> tuple[str, str, str, dict] | None:
        cat = self._cat_map.get(item["detected_category"])
        if not cat:
            return None
        candidates = renamer.get_candidates(
            item["name"], cat["media_type"], cat["api_pref"])
        if len(candidates) == 1:
            with_year = cat["media_type"] in ("movie", "anime_film")
            chosen = sanitize_windows_name(candidates[0].display(with_year))
            return (item["name"], chosen, cat["media_type"],
                    Renamer.candidate_meta(candidates[0]))
        return None

    def _safe_batch_size(self) -> int:
        prefs = {
            self._cat_map[item["detected_category"]]["api_pref"]
            for item in self._items
            if item["detected_category"] in self._cat_map
        }
        if not prefs:
            return 10
        return min(_BATCH_LIMITS.get(p, 10) for p in prefs)
