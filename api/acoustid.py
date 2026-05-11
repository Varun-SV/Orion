"""
AcoustID fingerprint-lookup client.

Flow:
  1. Call fingerprint_file(path) → (chromaprint, duration_seconds)
     Requires the `fpcalc` binary (part of Chromaprint).
  2. Call lookup(fingerprint, duration, api_key) → list of AcoustIDResult
     Each result carries one or more MusicBrainz recording IDs.

AcoustID API is free; register at https://acoustid.org/login to get a key.
The test key "8XaBELgH" is for development only and is rate-limited.
"""
from __future__ import annotations
import json
import logging
import shutil
import subprocess
import requests

log = logging.getLogger(__name__)

_ACOUSTID_URL = "https://api.acoustid.org/v2/lookup"
_TEST_KEY     = "8XaBELgH"


class AcoustIDResult:
    __slots__ = ("score", "recording_mbids")

    def __init__(self, score: float, recording_mbids: list[str]) -> None:
        self.score           = score
        self.recording_mbids = recording_mbids


def fpcalc_available() -> bool:
    return shutil.which("fpcalc") is not None


def fingerprint_file(path: str, max_seconds: int = 120) -> tuple[str, int] | None:
    """
    Run fpcalc on *path* and return (fingerprint_string, duration_in_seconds).
    Returns None if fpcalc is not installed or the file cannot be processed.
    """
    fpcalc = shutil.which("fpcalc")
    if not fpcalc:
        return None
    try:
        result = subprocess.run(
            [fpcalc, "-json", "-length", str(max_seconds), path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log.warning("fpcalc error for %s: %s", path, result.stderr[:200])
            return None
        data = json.loads(result.stdout)
        return data["fingerprint"], int(data.get("duration", 0))
    except Exception as exc:
        log.warning("fingerprint_file failed for %s: %s", path, exc)
        return None


def lookup(fingerprint: str, duration: int,
           api_key: str = _TEST_KEY) -> list[AcoustIDResult]:
    """
    Submit fingerprint to AcoustID and return matches with MusicBrainz IDs.
    """
    if not api_key:
        api_key = _TEST_KEY
    try:
        r = requests.get(_ACOUSTID_URL, params={
            "client":      api_key,
            "meta":        "recordings",
            "fingerprint": fingerprint,
            "duration":    duration,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
        out: list[AcoustIDResult] = []
        for result in data.get("results", []):
            score  = result.get("score", 0.0)
            mbids  = [rec["id"] for rec in result.get("recordings", [])
                      if "id" in rec]
            if mbids:
                out.append(AcoustIDResult(score=score, recording_mbids=mbids))
        return out
    except Exception as exc:
        log.warning("AcoustID lookup failed: %s", exc)
        return []
