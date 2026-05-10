"""
Scans source folders, detects categories from folder structure,
populates the database with scan items.
"""
from __future__ import annotations
import re
from pathlib import Path
from guessit import guessit as _guessit
from core.utils import collect_movie_leaves, is_series_folder, has_video_files, VIDEO_EXTS
from core.database import Database


# Compiled at module level — one-time cost
_ANIME_HINTS  = re.compile(r"anime|manga|ova|isekai|shounen|seinen|shojo", re.I)
_SERIES_HINTS = re.compile(r"series|shows?|tv", re.I)
_MOVIE_HINTS  = re.compile(r"movies?|films?|cinema", re.I)


class ScanResult:
    def __init__(self, path: str, name: str, item_type: str,
                 category: str, parent_path: str = "", is_leaf: bool = True):
        self.path        = path
        self.name        = name
        self.item_type   = item_type   # 'folder' | 'file'
        self.category    = category
        self.parent_path = parent_path
        self.is_leaf     = is_leaf


class Scanner:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ── Public ─────────────────────────────────────────────────────────
    def scan(self, source_folder_id: int, root: Path,
             categories: list[dict],
             progress_cb=None,
             deep: bool = False) -> list[ScanResult]:
        """
        Walk root, detect categories, collect leaf items.
        deep=True uses guessit on video filenames for more accurate
        category detection instead of folder-name regex.
        progress_cb(message: str) called for UI updates.
        """
        results: list[ScanResult] = []

        try:
            top_level = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except PermissionError:
            return results

        for child in top_level:
            if not child.is_dir():
                continue
            if progress_cb:
                prefix = "Deep scanning" if deep else "Scanning"
                progress_cb(f"{prefix} {child.name}…")

            category = (self._detect_category_deep(child, categories) if deep
                        else self._detect_category(child, categories))

            media_type = self._category_media_type(category, categories)
            if media_type in ("movie", "anime_film"):
                leaves = collect_movie_leaves(child)
                if len(leaves) == 1 and leaves[0] == child:
                    r = ScanResult(str(child), child.name, "folder", category)
                    results.append(r)
                    self._db.add_scan_item(source_folder_id, str(child),
                                           child.name, "folder", category, "", True)
                else:
                    for leaf in leaves:
                        r = ScanResult(str(leaf), leaf.name, "folder",
                                       category, str(child), True)
                        results.append(r)
                        self._db.add_scan_item(source_folder_id, str(leaf),
                                               leaf.name, "folder", category,
                                               str(child), True)
            else:
                r = ScanResult(str(child), child.name, "folder", category)
                results.append(r)
                self._db.add_scan_item(source_folder_id, str(child),
                                       child.name, "folder", category, "", True)

        return results

    def detect_categories_from_scan(self, root: Path) -> list[dict]:
        """
        Fast pre-scan: inspect top-level subfolder names with regex heuristics
        and suggest categories for the user to confirm.
        """
        suggestions = []
        try:
            for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
                if not child.is_dir():
                    continue
                media_type = self._infer_type(child)
                suggestions.append({
                    "name":        child.name,
                    "media_type":  media_type,
                    "api_pref":    "anilist" if "anime" in media_type else "tmdb",
                    "source_root": str(root),
                })
        except PermissionError:
            pass
        return suggestions

    def deep_scan_categories(self, root: Path,
                              progress_cb=None) -> list[dict]:
        """
        Deep pre-scan: walk all video files inside each top-level subfolder,
        run guessit on up to 50 filenames, build a consensus media_type.
        More accurate than detect_categories_from_scan for folders whose
        names don't match obvious keywords.
        """
        suggestions = []
        try:
            for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
                if not child.is_dir():
                    continue
                if progress_cb:
                    progress_cb(f"Deep scanning {child.name}…")
                video_names = [
                    p.name for p in child.rglob("*")
                    if p.is_file() and p.suffix.lower() in VIDEO_EXTS
                ]
                media_type = (self._consensus_from_files(child, video_names)
                              if video_names else self._infer_type(child))
                suggestions.append({
                    "name":        child.name,
                    "media_type":  media_type,
                    "api_pref":    "anilist" if "anime" in media_type else "tmdb",
                    "source_root": str(root),
                })
        except PermissionError:
            pass
        return suggestions

    # ── Internal ───────────────────────────────────────────────────────
    def _detect_category(self, folder: Path, categories: list[dict]) -> str:
        """Match folder against known categories, fall back to name-regex."""
        name_lower = folder.name.lower()
        for cat in categories:
            if cat["name"].lower() in name_lower or name_lower in cat["name"].lower():
                return cat["name"]
        return self._infer_type(folder)

    def _detect_category_deep(self, folder: Path,
                               categories: list[dict]) -> str:
        """Match folder against known categories, fall back to guessit consensus."""
        name_lower = folder.name.lower()
        for cat in categories:
            if cat["name"].lower() in name_lower or name_lower in cat["name"].lower():
                return cat["name"]
        video_names = [
            p.name for p in folder.rglob("*")
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS
        ]
        return (self._consensus_from_files(folder, video_names)
                if video_names else self._infer_type(folder))

    def _infer_type(self, folder: Path) -> str:
        name = folder.name.lower()
        if _ANIME_HINTS.search(name):
            return "anime"
        if _SERIES_HINTS.search(name):
            return "series"
        if _MOVIE_HINTS.search(name):
            return "movie"
        if is_series_folder(folder):
            return "series"
        return "movie"

    def _consensus_from_files(self, folder: Path,
                               video_names: list[str]) -> str:
        """
        Run guessit on up to 50 video filenames and tally votes for
        movie / series / anime to pick the most likely media type.
        """
        votes: dict[str, int] = {"movie": 0, "series": 0, "anime": 0}
        for name in video_names[:50]:
            info        = _guessit(name)
            has_episode = bool(info.get("episode") or info.get("season"))
            is_anime    = bool(_ANIME_HINTS.search(name) or
                               _ANIME_HINTS.search(folder.name))
            if is_anime:
                votes["anime"] += 1
            elif has_episode:
                votes["series"] += 1
            else:
                votes["movie"] += 1

        if is_series_folder(folder):
            votes["series"] += max(1, len(video_names[:50]) // 3)

        best = max(votes, key=lambda k: votes[k])
        return best if votes[best] > 0 else self._infer_type(folder)

    def _category_media_type(self, category_name: str,
                             categories: list[dict]) -> str:
        for cat in categories:
            if cat["name"] == category_name:
                return cat["media_type"]
        return "movie"
