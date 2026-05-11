"""
Music scan worker — walks source folders for audio files, reads embedded
tags, and falls back to AcoustID fingerprinting + MusicBrainz lookup when
tags are absent or incomplete.

Emits:
  progress(current, total, filename)
  item_found(dict)    — one per identified file
  complete(int)       — total files found
  error(str)
"""
from __future__ import annotations
import os
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from core.database import Database
from api.musicbrainz import MusicBrainzClient, RecordingResult
from api.acoustid import fingerprint_file, lookup as acoustid_lookup, fpcalc_available

_AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".aac", ".opus",
               ".wma", ".alac", ".aiff"}


def _read_tags(path: str) -> dict:
    """
    Try to read ID3/Vorbis/MP4 tags with mutagen.
    Returns a dict with keys: title, artist, album, year, track_number, duration.
    Falls back to empty strings / 0 if mutagen is absent or the file has no tags.
    """
    try:
        from mutagen import File as MFile  # type: ignore
        f = MFile(path, easy=True)
        if f is None:
            return {}
        info = f.info if hasattr(f, "info") else None
        return {
            "title":        str((f.get("title")        or [""])[0]),
            "artist":       str((f.get("artist")       or [""])[0]),
            "album":        str((f.get("album")        or [""])[0]),
            "year":         str((f.get("date")         or [""])[0])[:4],
            "track_number": str((f.get("tracknumber")  or [""])[0]),
            "disc_number":  str((f.get("discnumber")   or [""])[0]),
            "duration":     getattr(info, "length", 0.0) if info else 0.0,
        }
    except Exception:
        return {}


def _tags_complete(tags: dict) -> bool:
    return bool(tags.get("title") and tags.get("artist") and tags.get("album"))


class MusicScanWorker(QThread):
    progress   = pyqtSignal(int, int, str)
    item_found = pyqtSignal(dict)
    complete   = pyqtSignal(int)
    error      = pyqtSignal(str)

    def __init__(self, db: Database,
                 source_folders: list[dict],
                 acoustid_key: str = "",
                 use_fingerprint: bool = True) -> None:
        super().__init__()
        self._db              = db
        self._folders         = source_folders
        self._acoustid_key    = acoustid_key
        self._use_fingerprint = use_fingerprint and fpcalc_available()
        self._abort           = False
        self._mb              = MusicBrainzClient()

    def stop(self) -> None:
        self._abort = True

    def run(self) -> None:
        files = self._collect_files()
        total = len(files)

        for i, fpath in enumerate(files):
            if self._abort:
                break
            self.progress.emit(i + 1, total, Path(fpath).name)
            try:
                item = self._identify(fpath)
            except Exception as exc:
                self.error.emit(f"{Path(fpath).name}: {exc}")
                continue
            if item:
                self._db.upsert_music_item(**item)
                self.item_found.emit(item)

        self.complete.emit(total)

    def _collect_files(self) -> list[str]:
        files: list[str] = []
        for sf in self._folders:
            root = Path(sf["path"])
            if not root.exists():
                continue
            for dirpath, _, filenames in os.walk(root):
                for fn in filenames:
                    if Path(fn).suffix.lower() in _AUDIO_EXTS:
                        files.append(str(Path(dirpath) / fn))
        return files

    def _identify(self, fpath: str) -> dict | None:
        tags = _read_tags(fpath)
        confidence = 0.0
        mbid = tags.get("mbid", "")

        if _tags_complete(tags):
            confidence = 0.8
        elif self._use_fingerprint:
            fp_result = fingerprint_file(fpath)
            if fp_result:
                fingerprint, duration = fp_result
                results = acoustid_lookup(fingerprint, duration, self._acoustid_key)
                if results and results[0].score >= 0.7:
                    top     = results[0]
                    rec     = self._mb.get_recording(top.recording_mbids[0])
                    if rec:
                        tags["title"]        = rec.title
                        tags["artist"]       = rec.artist
                        tags["album"]        = rec.album
                        tags["year"]         = rec.year
                        tags["track_number"] = rec.track_number
                        tags["disc_number"]  = rec.disc_number
                        confidence           = top.score
                        mbid                 = rec.mbid
        else:
            # Fall back to text search by filename stem
            stem = Path(fpath).stem
            recs = self._mb.search_recordings(stem)
            if recs:
                rec = recs[0]
                tags.setdefault("title",        rec.title)
                tags.setdefault("artist",       rec.artist)
                tags.setdefault("album",        rec.album)
                tags.setdefault("year",         rec.year)
                tags.setdefault("track_number", rec.track_number)
                confidence = rec.score
                mbid       = rec.mbid

        p = Path(fpath)
        return {
            "source_path":  fpath,
            "filename":     p.name,
            "title":        tags.get("title", ""),
            "artist":       tags.get("artist", ""),
            "album":        tags.get("album", ""),
            "year":         tags.get("year", ""),
            "track_number": tags.get("track_number", ""),
            "disc_number":  tags.get("disc_number", ""),
            "duration":     tags.get("duration", 0.0),
            "mbid":         mbid,
            "confidence":   confidence,
            "status":       "identified" if confidence >= 0.5 else "pending",
        }
