"""
AniDB client — supplementary anime + episode data.
AniDB's HTTP API requires a registered client ID.
Client must be registered at: https://anidb.net/software/add

Without registration the ban rate is very aggressive.
This client is used only for episode title fallback when AniList
doesn't have the data.
"""
from __future__ import annotations
import time
import xml.etree.ElementTree as ET
import requests

ANIDB_URL = "http://api.anidb.net:9001/httpapi"


class AniDBClient:
    def __init__(self, client: str = "orion",
                 client_ver: int = 1) -> None:
        self._client  = client
        self._ver     = client_ver
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": f"{client}/{client_ver}"})

    def _params(self, **extra) -> dict:
        return {"client": self._client, "clientver": self._ver,
                "protover": 1, **extra}

    def _request(self, params: dict) -> requests.Response:
        """GET with exponential-backoff retry on 429 / transient errors."""
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
        """Search AniDB for an anime by title. Returns basic info dicts."""
        try:
            r = self._request(self._params(
                request="anime", adb_request="search",
                pagelen=6, query=title))
            root = ET.fromstring(r.text)
            results = []
            for anime in root.findall(".//anime"):
                results.append({
                    "aid":   anime.get("id"),
                    "title": anime.findtext("titles/title[@xml:lang='en']") or
                             anime.findtext("titles/title") or "",
                })
            return results
        except Exception:
            return []

    def get_episode_title(self, aid: int, episode_num: int) -> str:
        """Fetch an episode title from AniDB by anime ID and episode number."""
        try:
            r = self._request(self._params(request="anime", aid=aid))
            root = ET.fromstring(r.text)
            for ep in root.findall(".//episode"):
                epno_el = ep.find("epno")
                if epno_el is not None and epno_el.text == str(episode_num):
                    return ep.findtext("title[@xml:lang='en']") or ep.findtext("title") or ""
        except Exception:
            pass
        return ""
