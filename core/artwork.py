"""
Artwork download — poster.jpg / cover.jpg sidecars next to organized media.

Sources:
  Video : TMDb poster (w185 preview URL upgraded to w500) or AniList cover
  Music : Cover Art Archive front cover, looked up by MusicBrainz release ID
  Books : Open Library cover by ISBN

Existing image files are never overwritten.
"""
from __future__ import annotations
import logging
from pathlib import Path
import requests

log = logging.getLogger(__name__)

_CAA_FRONT = "https://coverartarchive.org/release/{mbid}/front-500"
_OL_COVER  = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"


def download_image(url: str, dest: Path) -> bool:
    """Download *url* to *dest*. Skips if dest exists. True on success."""
    if dest.exists():
        return True
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        if not r.content or "image" not in r.headers.get("Content-Type", "image"):
            return False
        dest.write_bytes(r.content)
        return True
    except Exception as exc:
        log.warning("Artwork download failed %s: %s", url, exc)
        return False


def save_poster(poster_url: str, dest: Path) -> bool:
    """Save a video poster, upgrading TMDb thumbnail URLs to w500."""
    url = poster_url.replace("/t/p/w185/", "/t/p/w500/")
    return download_image(url, dest)


def save_album_cover(release_mbid: str, dest: Path) -> bool:
    """Save the Cover Art Archive front cover for a MusicBrainz release."""
    if not release_mbid:
        return False
    return download_image(_CAA_FRONT.format(mbid=release_mbid), dest)


def save_book_cover(isbn: str, dest: Path) -> bool:
    """Save the Open Library cover for an ISBN."""
    if not isbn:
        return False
    return download_image(_OL_COVER.format(isbn=isbn), dest)
