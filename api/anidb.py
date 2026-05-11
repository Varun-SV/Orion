"""
AniDB HTTP API client — anime search + episode title fallback.

Authentication: no API key. AniDB uses a registered client name
('client' parameter) that you register at anidb.net/software/add.
Rate limit: 1 request per 2 seconds — enforced here via a class-level
throttle so all instances share the same slot.
"""
from __future__ import annotations
import threading
import time
import xml.etree.ElementTree as ET
import requests

ANIDB_URL = "http://api.anidb.net:9001/httpapi"

_DEFAULT_CLIENT = "orion"


class AniDBClient:
    # Class-level throttle: AniDB allows max 1 request per 2 seconds
    _lock              = threading.Lock()
    _last_request_time = 0.0
    _MIN_INTERVAL      = 2.1   # slightly above the 2 s hard limit

    def __init__(self, client: str = _DEFAULT_CLIENT,
                 client_ver: int = 1) -> None:
        self._client  = client or _DEFAULT_CLIENT
        self._ver     = client_ver
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": f"{self._client}/{self._ver}"})

    def _params(self, **extra) -> dict:
        return {"client": self._client, "clientver": self._ver,
                "protover": 1, **extra}

    def _request(self, params: dict) -> requests.Response:
        """Throttle to 1 req/2 s, then GET with exponential-backoff retry."""
        with AniDBClient._lock:
            elapsed = time.monotonic() - AniDBClient._last_request_time
            if elapsed < self._MIN_INTERVAL:
                time.sleep(self._MIN_INTERVAL - elapsed)
            AniDBClient._last_request_time = time.monotonic()

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                r = self._session.get(ANIDB_URL, params=params, timeout=10)
                r.raise_for_status()
                return r
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    time.sleep(5 * 2 ** attempt)   # 5 s, 10 s, 20 s
                    last_exc = exc
                else:
                    raise
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise last_exc or RuntimeError("AniDB request failed after retries")

    def search_anime(self, title: str) -> list[dict]:
        """Search AniDB by title. Returns list of {aid, title} dicts."""
        try:
            r    = self._request(self._params(
                request="anime", adb_request="search",
                pagelen=6, query=title))
            root = ET.fromstring(r.text)
            out  = []
            for anime in root.findall(".//anime"):
                out.append({
                    "aid":   anime.get("id"),
                    "title": (anime.findtext("titles/title[@xml:lang='en']")
                              or anime.findtext("titles/title") or ""),
                })
            return out
        except Exception:
            return []

    def get_episode_title(self, aid: int, episode_num: int) -> str:
        """Fetch a single episode title by anime ID and episode number."""
        try:
            r    = self._request(self._params(request="anime", aid=aid))
            root = ET.fromstring(r.text)
            for ep in root.findall(".//episode"):
                epno = ep.find("epno")
                if epno is not None and epno.text == str(episode_num):
                    return (ep.findtext("title[@xml:lang='en']")
                            or ep.findtext("title") or "")
        except Exception:
            pass
        return ""
