"""
Kodi/Jellyfin-compatible NFO sidecar generation.

Servers that find an NFO next to the media use it directly instead of
re-scraping, so libraries pick up correct titles, years, plots, and
provider IDs immediately — even offline.

Layout written by Orion:
  Movies      : <Movie folder>/movie.nfo   + poster.jpg
  Series/Anime: <Series folder>/tvshow.nfo + poster.jpg
  Music       : <Artist>/artist.nfo, <Artist>/<Album>/album.nfo + cover.jpg

Existing NFO/artwork files are never overwritten.
"""
from __future__ import annotations
import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from core import artwork

log = logging.getLogger(__name__)

# Candidate.source → NFO <uniqueid type=…> value
_PROVIDER_IDS = {"tmdb": "tmdb", "anilist": "anilist", "anidb": "anidb"}


def _write_xml(root: ET.Element, dest: Path) -> bool:
    """Write an XML tree as a UTF-8 NFO. Never overwrites. True on success."""
    if dest.exists():
        return True
    try:
        tree = ET.ElementTree(root)
        ET.indent(tree)
        tree.write(dest, encoding="utf-8", xml_declaration=True)
        return True
    except Exception as exc:
        log.warning("NFO write failed %s: %s", dest, exc)
        return False


def _add(parent: ET.Element, tag: str, text) -> None:
    if text is None or text == "":
        return
    el = ET.SubElement(parent, tag)
    el.text = str(text)


def _video_root(tag: str, meta: dict) -> ET.Element:
    root = ET.Element(tag)
    _add(root, "title", meta.get("title"))
    _add(root, "year",  meta.get("year"))
    _add(root, "plot",  meta.get("overview"))
    provider = _PROVIDER_IDS.get(meta.get("source", ""))
    if provider and meta.get("id"):
        uid = ET.SubElement(root, "uniqueid",
                            {"type": provider, "default": "true"})
        uid.text = str(meta["id"])
    return root


# ── Video ──────────────────────────────────────────────────────────────
def write_video_sidecars(folder: Path, media_type: str, meta: dict) -> bool:
    """
    Write movie.nfo / tvshow.nfo + poster.jpg into a moved media folder.
    *media_type* is the Orion category media type (movie, series, anime,
    anime_film, web_series). Returns True if the NFO was written/present.
    """
    if not folder.is_dir() or not meta.get("title"):
        return False
    tag  = "movie" if media_type in ("movie", "anime_film") else "tvshow"
    ok   = _write_xml(_video_root(tag, meta), folder / f"{tag}.nfo")
    if meta.get("poster_url"):
        artwork.save_poster(meta["poster_url"], folder / "poster.jpg")
    return ok


# ── Music ──────────────────────────────────────────────────────────────
def write_artist_nfo(artist_dir: Path, artist: str) -> bool:
    if not artist_dir.is_dir() or not artist:
        return False
    root = ET.Element("artist")
    _add(root, "name", artist)
    return _write_xml(root, artist_dir / "artist.nfo")


def write_album_nfo(album_dir: Path, album: str, artist: str,
                    year: str = "", release_mbid: str = "") -> bool:
    if not album_dir.is_dir() or not album:
        return False
    root = ET.Element("album")
    _add(root, "title",  album)
    _add(root, "artist", artist)
    _add(root, "year",   year)
    _add(root, "musicbrainzalbumid", release_mbid)
    return _write_xml(root, album_dir / "album.nfo")
