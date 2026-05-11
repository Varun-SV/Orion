"""
Rename orchestration: fetches API candidates, persists choices,
applies sanitization before any path is constructed.
"""
from __future__ import annotations
import logging
from guessit import guessit
from core.database import Database
from core.utils import sanitize_windows_name
from api.tmdb import TMDbClient, Candidate
from api.anilist import AniListClient
from api.anidb import AniDBClient

log = logging.getLogger(__name__)


class Renamer:
    def __init__(self, db: Database,
                 tmdb: TMDbClient,
                 anilist: AniListClient,
                 anidb: AniDBClient | None = None) -> None:
        self._db      = db
        self._tmdb    = tmdb
        self._anilist = anilist
        self._anidb   = anidb

    # ── Choice persistence ─────────────────────────────────────────────
    def get_choice(self, original_name: str) -> str | None:
        row = self._db.get_rename_choice(original_name)
        if row:
            return sanitize_windows_name(row["chosen_name"])
        return None

    def save_choice(self, original_name: str, chosen_name: str,
                    media_type: str = "", source: str = "user") -> None:
        self._db.set_rename_choice(
            original_name, sanitize_windows_name(chosen_name), media_type, source)

    def clear_choice(self, original_name: str) -> None:
        self._db.delete_rename_choice(original_name)

    # ── API candidate fetch ────────────────────────────────────────────
    def get_candidates(self, folder_name: str,
                       media_type: str,
                       api_pref: str = "tmdb") -> list[Candidate]:
        """
        Parse folder name with guessit, then query appropriate APIs.
        api_pref controls which services are used: tmdb | anilist | anidb | both
        'both' queries all services applicable to the media type.
        Returns deduplicated list of Candidate objects.
        """
        info  = guessit(folder_name)
        title = str(info.get("title", folder_name))
        year  = info.get("year")

        candidates: list[Candidate] = []

        # AniList — no key needed, always available for anime
        if media_type in ("anime", "anime_film") or api_pref in ("anilist", "both"):
            candidates += self._anilist.search_anime(title)

        # AniDB — registered client name required; used for anime search + episode fallback
        if api_pref in ("anidb", "both") and self._anidb:
            for result in self._anidb.search_anime(title):
                if result.get("title"):
                    candidates.append(Candidate(
                        name=result["title"],
                        year=None,
                        media_type="anime",
                        tmdb_id=None,
                        source="anidb",
                        extra={"aid": result.get("aid")},
                    ))

        # TMDb — API key required
        if media_type == "movie" or api_pref in ("tmdb", "both"):
            candidates += self._tmdb.search_movie(title, year)

        if media_type == "series" or (api_pref in ("tmdb", "both") and not candidates):
            candidates += self._tmdb.search_tv(title, year)

        # Deduplicate by (name.lower(), year)
        seen: set[tuple] = set()
        out:  list[Candidate] = []
        for c in candidates:
            key = (c.name.lower(), c.year)
            if key not in seen:
                seen.add(key)
                out.append(c)
        return out

    # ── Format helpers ─────────────────────────────────────────────────
    @staticmethod
    def format_name(candidate: Candidate, with_year: bool = True) -> str:
        name = sanitize_windows_name(candidate.name)
        if with_year and candidate.year:
            return f"{name} ({candidate.year})"
        return name
