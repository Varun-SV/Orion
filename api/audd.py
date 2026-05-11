"""
AudD music recognition API — identifies music from an audio file.
Docs: https://docs.audd.io/

Free tier: 100 recognitions / day.
Register at https://dashboard.audd.io to get an API token.

Usage:
  result = AudDClient(api_token).recognize_file("/path/to/song.mp3")
  if result:
      print(result.artist, result.title, result.album)
"""
from __future__ import annotations
import logging
import requests

log = logging.getLogger(__name__)

_AUDD_URL = "https://api.audd.io/"


class AudDResult:
    __slots__ = ("artist", "title", "album", "release_date", "label", "song_link")

    def __init__(self, artist: str, title: str, album: str = "",
                 release_date: str = "", label: str = "",
                 song_link: str = "") -> None:
        self.artist       = artist
        self.title        = title
        self.album        = album
        self.release_date = release_date
        self.label        = label
        self.song_link    = song_link

    @property
    def year(self) -> str:
        return self.release_date[:4] if self.release_date else ""


class AudDClient:
    def __init__(self, api_token: str = "") -> None:
        self._token   = api_token
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "Orion/1.0"

    def recognize_file(self, path: str,
                       max_bytes: int = 512 * 1024) -> AudDResult | None:
        """
        POST up to *max_bytes* of the audio file to AudD for recognition.
        Returns AudDResult on success, None on failure or no match.
        """
        try:
            with open(path, "rb") as fh:
                data = fh.read(max_bytes)

            payload = {"return": "apple_music,spotify"}
            if self._token:
                payload["api_token"] = self._token

            r = self._session.post(
                _AUDD_URL,
                data=payload,
                files={"file": ("audio", data, "application/octet-stream")},
                timeout=20,
            )
            r.raise_for_status()
            body = r.json()

            if body.get("status") != "success" or not body.get("result"):
                return None

            res = body["result"]
            return AudDResult(
                artist       = res.get("artist", ""),
                title        = res.get("title", ""),
                album        = res.get("album", ""),
                release_date = res.get("release_date", ""),
                label        = res.get("label", ""),
                song_link    = res.get("song_link", ""),
            )
        except Exception as exc:
            log.warning("AudD recognition failed for %s: %s", path, exc)
            return None
