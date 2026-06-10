"""
MusicBrainz API client — free, no API key required.
Rate limit: 1 request per second (enforced via class-level throttle).
User-Agent is required; MusicBrainz rejects unidentified bots.

Typical flow:
  1. search_recordings(title, artist) → list of RecordingResult
  2. get_recording(mbid)              → full metadata including release, track #
"""
from __future__ import annotations
import threading
import time
import logging
import requests

log = logging.getLogger(__name__)

_MB_BASE   = "https://musicbrainz.org/ws/2"
_USER_AGENT = "Orion/1.0 (https://github.com/Varun-SV/Orion)"


class RecordingResult:
    __slots__ = ("mbid", "title", "artist", "album", "year",
                 "track_number", "disc_number", "score")

    def __init__(self, mbid: str, title: str, artist: str,
                 album: str = "", year: str = "",
                 track_number: str = "", disc_number: str = "",
                 score: float = 0.0) -> None:
        self.mbid         = mbid
        self.title        = title
        self.artist       = artist
        self.album        = album
        self.year         = year
        self.track_number = track_number
        self.disc_number  = disc_number
        self.score        = score

    def jellyfin_path(self) -> tuple[str, str, str]:
        """Returns (artist, album_with_year, filename_stem) for Jellyfin layout."""
        album_dir = f"{self.album} ({self.year})" if self.year else self.album
        if self.track_number:
            try:
                num = int(self.track_number.split("/")[0])
                stem = f"{num:02d} - {self.title}"
            except ValueError:
                stem = f"{self.track_number} - {self.title}"
        else:
            stem = self.title
        return self.artist, album_dir, stem


class MusicBrainzClient:
    _lock              = threading.Lock()
    _last_request_time = 0.0
    _MIN_INTERVAL      = 1.05  # 1 req/s; 1.05 to give a safety margin

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept":     "application/json",
        })

    def _get(self, endpoint: str, params: dict) -> dict:
        with MusicBrainzClient._lock:
            elapsed = time.monotonic() - MusicBrainzClient._last_request_time
            if elapsed < self._MIN_INTERVAL:
                time.sleep(self._MIN_INTERVAL - elapsed)
            MusicBrainzClient._last_request_time = time.monotonic()

        params["fmt"] = "json"
        for attempt in range(3):
            try:
                r = self._session.get(f"{_MB_BASE}/{endpoint}",
                                      params=params, timeout=10)
                if r.status_code == 503:
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                return r.json()
            except requests.RequestException as exc:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    log.warning("MusicBrainz request failed: %s", exc)
                    return {}
        return {}

    def search_recordings(self, title: str,
                          artist: str = "") -> list[RecordingResult]:
        """Text-search recordings. Returns up to 10 results."""
        query = f'recording:"{title}"'
        if artist:
            query += f' AND artistname:"{artist}"'
        data = self._get("recording", {"query": query, "limit": 10})
        out: list[RecordingResult] = []
        for rec in data.get("recordings", []):
            rel_list = rec.get("releases", [])
            album  = rel_list[0].get("title", "") if rel_list else ""
            year   = ""
            tnum   = ""
            dnum   = ""
            if rel_list:
                date = rel_list[0].get("date", "")
                year = date[:4] if date else ""
                media = rel_list[0].get("media", [])
                if media:
                    tnum = str(media[0].get("track-offset", 0) + 1) if media else ""
                    dnum = str(rel_list[0].get("media", [{}])[0]
                               .get("position", "")) if media else ""
            artists = [a["name"] for a in rec.get("artist-credit", [])
                       if isinstance(a, dict) and "name" in a]
            artist_str = ", ".join(artists)
            out.append(RecordingResult(
                mbid         = rec.get("id", ""),
                title        = rec.get("title", ""),
                artist       = artist_str,
                album        = album,
                year         = year,
                track_number = tnum,
                disc_number  = dnum,
                score        = rec.get("score", 0) / 100.0,
            ))
        return out

    def get_release_id(self, recording_mbid: str) -> str:
        """First release MBID for a recording — used for Cover Art Archive."""
        data = self._get(f"recording/{recording_mbid}", {"inc": "releases"})
        releases = data.get("releases", [])
        return releases[0].get("id", "") if releases else ""

    def get_recording(self, mbid: str) -> RecordingResult | None:
        """Fetch full metadata for a recording by MBID."""
        data = self._get(f"recording/{mbid}",
                         {"inc": "artists+releases+release-groups"})
        if not data or "id" not in data:
            return None

        rel_list = data.get("releases", [])
        album    = rel_list[0].get("title", "") if rel_list else ""
        year     = ""
        tnum     = ""
        dnum     = ""
        if rel_list:
            date = rel_list[0].get("date", "")
            year = date[:4] if date else ""
            media = rel_list[0].get("media", [])
            if media:
                tracks = media[0].get("tracks", [])
                if tracks:
                    tnum = str(tracks[0].get("number", ""))
                dnum = str(media[0].get("position", ""))

        artists = [a["name"] for a in data.get("artist-credit", [])
                   if isinstance(a, dict) and "name" in a]
        return RecordingResult(
            mbid         = mbid,
            title        = data.get("title", ""),
            artist       = ", ".join(artists),
            album        = album,
            year         = year,
            track_number = tnum,
            disc_number  = dnum,
            score        = 1.0,
        )
