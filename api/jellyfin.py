"""
Jellyfin / Emby API client — library search, refresh, series episodes.

Both servers expose the same (Emby-derived) REST API surface for everything
Orion needs, authenticated with an API key via the X-Emby-Token header:
  GET  /System/Info        — server name + version (connection test)
  POST /Library/Refresh    — trigger a full library scan
  GET  /Users              — resolve a user id for /Items queries
  GET  /Items              — recursive library search
  GET  /Shows/{id}/Episodes — episodes of a series (gap analysis)

Create an API key in the server dashboard:  Dashboard → API Keys.
"""
from __future__ import annotations
import logging
import requests

log = logging.getLogger(__name__)


class ServerItem:
    __slots__ = ("item_id", "name", "year", "item_type", "resolution", "path")

    def __init__(self, item_id: str, name: str, year: int | None,
                 item_type: str, resolution: str = "", path: str = "") -> None:
        self.item_id    = item_id
        self.name       = name
        self.year       = year
        self.item_type  = item_type   # 'Movie' | 'Series' | …
        self.resolution = resolution  # '4K' | '1080p' | '720p' | ''
        self.path       = path

    def display(self) -> str:
        base = f"{self.name} ({self.year})" if self.year else self.name
        return f"{base} · {self.resolution}" if self.resolution else base


def _resolution_label(height: int) -> str:
    if height >= 2000:
        return "4K"
    if height >= 1000:
        return "1080p"
    if height >= 700:
        return "720p"
    return f"{height}p" if height else ""


class JellyfinClient:
    def __init__(self, base_url: str, api_key: str,
                 server_type: str = "jellyfin") -> None:
        self._base = base_url.rstrip("/")
        self._type = server_type            # 'jellyfin' | 'emby'
        self._session = requests.Session()
        self._session.headers.update({
            "X-Emby-Token": api_key,
            "Accept":       "application/json",
        })
        self._user_id: str | None = None

    # ── Low level ──────────────────────────────────────────────────────
    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        r = self._session.get(f"{self._base}{endpoint}",
                              params=params or {}, timeout=10)
        r.raise_for_status()
        return r.json() if r.content else {}

    def _ensure_user(self) -> str:
        """Item queries need a user context; use the first user on the server."""
        if self._user_id is None:
            users = self._session.get(f"{self._base}/Users", timeout=10)
            users.raise_for_status()
            data = users.json()
            if not data:
                raise RuntimeError("Server has no users")
            self._user_id = data[0]["Id"]
        return self._user_id

    # ── Public ─────────────────────────────────────────────────────────
    def test_connection(self) -> tuple[bool, str]:
        """Returns (ok, human-readable message)."""
        try:
            info = self._get("/System/Info")
            name = info.get("ServerName", "server")
            ver  = info.get("Version", "?")
            label = "Emby" if self._type == "emby" else "Jellyfin"
            return True, f"Connected to {name} ({label} {ver})"
        except requests.exceptions.ConnectionError:
            return False, "Connection failed — check the URL"
        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            if code == 401:
                return False, "Unauthorized — check the API key"
            return False, f"Server returned HTTP {code}"
        except Exception as exc:
            return False, str(exc)

    def refresh_library(self) -> bool:
        """Trigger a full library scan. Returns True on success."""
        try:
            r = self._session.post(f"{self._base}/Library/Refresh", timeout=10)
            r.raise_for_status()
            return True
        except Exception as exc:
            log.warning("Library refresh failed: %s", exc)
            return False

    def search_items(self, term: str,
                     include_types: str = "Movie,Series") -> list[ServerItem]:
        """Search the library recursively. Returns matching items with resolution."""
        try:
            data = self._get("/Items", {
                "userId":           self._ensure_user(),
                "searchTerm":       term,
                "IncludeItemTypes": include_types,
                "Recursive":        "true",
                "fields":           "ProductionYear,Path,MediaSources",
                "limit":            10,
            })
        except Exception as exc:
            log.warning("Server search failed: %s", exc)
            return []
        return [self._parse_item(i) for i in data.get("Items", [])]

    def get_all_series(self) -> list[ServerItem]:
        """All series in the library, sorted by name."""
        try:
            data = self._get("/Items", {
                "userId":           self._ensure_user(),
                "IncludeItemTypes": "Series",
                "Recursive":        "true",
                "fields":           "ProductionYear",
                "sortBy":           "SortName",
            })
        except Exception as exc:
            log.warning("Series list failed: %s", exc)
            return []
        return [self._parse_item(i) for i in data.get("Items", [])]

    def get_episodes(self, series_id: str) -> set[tuple[int, int]]:
        """Return {(season, episode)} pairs the server has for a series."""
        try:
            data = self._get(f"/Shows/{series_id}/Episodes", {
                "userId": self._ensure_user(),
            })
        except Exception as exc:
            log.warning("Episode list failed: %s", exc)
            return set()
        out: set[tuple[int, int]] = set()
        for ep in data.get("Items", []):
            s = ep.get("ParentIndexNumber")
            e = ep.get("IndexNumber")
            if s is not None and e is not None:
                out.add((int(s), int(e)))
        return out

    # ── Internal ───────────────────────────────────────────────────────
    @staticmethod
    def _parse_item(item: dict) -> ServerItem:
        height = 0
        for src in item.get("MediaSources") or []:
            for stream in src.get("MediaStreams") or []:
                if stream.get("Type") == "Video":
                    height = max(height, int(stream.get("Height") or 0))
        return ServerItem(
            item_id    = item.get("Id", ""),
            name       = item.get("Name", ""),
            year       = item.get("ProductionYear"),
            item_type  = item.get("Type", ""),
            resolution = _resolution_label(height),
            path       = item.get("Path", ""),
        )
