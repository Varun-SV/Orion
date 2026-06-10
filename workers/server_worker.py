"""
QThreads for Jellyfin/Emby server calls so the UI never blocks on the
network: connection test, duplicate lookup, series listing, and
missing-episode gap analysis.
"""
from __future__ import annotations
from PyQt6.QtCore import QThread, pyqtSignal

from api.jellyfin import JellyfinClient
from api.tmdb import TMDbClient


class ServerTestWorker(QThread):
    """Settings → Server → Test connection."""
    result = pyqtSignal(bool, str)   # ok, message

    def __init__(self, client: JellyfinClient) -> None:
        super().__init__()
        self._client = client

    def run(self) -> None:
        ok, msg = self._client.test_connection()
        self.result.emit(ok, msg)


class DupCheckWorker(QThread):
    """Searches the server library for an item being identified."""
    found = pyqtSignal(str, list)    # query, list[ServerItem]

    def __init__(self, client: JellyfinClient, query: str,
                 include_types: str = "Movie,Series") -> None:
        super().__init__()
        self._client = client
        self._query  = query
        self._types  = include_types

    def run(self) -> None:
        items = self._client.search_items(self._query, self._types)
        self.found.emit(self._query, items)


class SeriesListWorker(QThread):
    """Fetches every series in the server library (gap panel)."""
    loaded = pyqtSignal(list)        # list[ServerItem]
    error  = pyqtSignal(str)

    def __init__(self, client: JellyfinClient) -> None:
        super().__init__()
        self._client = client

    def run(self) -> None:
        try:
            self.loaded.emit(self._client.get_all_series())
        except Exception as exc:
            self.error.emit(str(exc))


class GapAnalysisWorker(QThread):
    """
    Diffs one library series against TMDb:
      server episodes (have) vs TMDb season listings (want) → missing rows.
    """
    progress = pyqtSignal(str)
    complete = pyqtSignal(list, int)  # [(season, episode, title)], total_expected
    error    = pyqtSignal(str)

    def __init__(self, client: JellyfinClient, tmdb: TMDbClient,
                 series_id: str, name: str, year: int | None) -> None:
        super().__init__()
        self._client = client
        self._tmdb   = tmdb
        self._sid    = series_id
        self._name   = name
        self._year   = year

    def run(self) -> None:
        try:
            self.progress.emit("Fetching library episodes…")
            have = self._client.get_episodes(self._sid)

            self.progress.emit("Matching series on TMDb…")
            results = self._tmdb.search_tv(self._name, self._year)
            if not results and self._year:
                results = self._tmdb.search_tv(self._name)
            if not results or not results[0].tmdb_id:
                self.error.emit("Series not found on TMDb — "
                                "check the TMDb API key in Settings.")
                return

            tv_id   = results[0].tmdb_id
            details = self._tmdb.get_tv_details(tv_id)
            missing: list[tuple[int, int, str]] = []
            total   = 0
            for season in details.get("seasons", []):
                n = season.get("season_number", 0)
                if n == 0:          # skip specials
                    continue
                self.progress.emit(f"Checking Season {n:02d}…")
                for ep in self._tmdb.get_season_episodes(tv_id, n):
                    e = ep.get("episode_number")
                    if e is None:
                        continue
                    total += 1
                    if (n, e) not in have:
                        missing.append((n, e, ep.get("name", "")))
            self.complete.emit(missing, total)
        except Exception as exc:
            self.error.emit(str(exc))
