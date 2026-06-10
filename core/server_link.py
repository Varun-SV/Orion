"""
Media-server glue — builds a JellyfinClient from saved settings and
provides the fire-and-forget "refresh library after move" hook.

Settings live in the database settings table (server_url, server_type,
server_autorefresh); the API key lives in the OS keychain under the
service name 'media_server'.
"""
from __future__ import annotations
import threading

from api.jellyfin import JellyfinClient
from core.config import Config
from core.database import Database

KEYRING_SERVICE = "media_server"


def get_client(db: Database, config: Config) -> JellyfinClient | None:
    """Return a configured client, or None if the server isn't set up."""
    url = db.setting_get("server_url").strip()
    key = config.get_api_key(KEYRING_SERVICE)
    if not url or not key:
        return None
    return JellyfinClient(url, key, db.setting_get("server_type", "jellyfin"))


def is_configured(db: Database, config: Config) -> bool:
    return get_client(db, config) is not None


def refresh_after_move(db: Database, config: Config) -> bool:
    """
    Trigger a library refresh in a background thread if a server is
    configured and auto-refresh is enabled. Returns True if a refresh
    was started (the result lands in the activity log).
    """
    if db.setting_get("server_autorefresh", "1") != "1":
        return False
    client = get_client(db, config)
    if client is None:
        return False

    url = db.setting_get("server_url")

    def _go() -> None:
        ok = client.refresh_library()
        db.add_log("server_refresh", url,
                   "library refresh triggered" if ok else "refresh failed",
                   "ok" if ok else "error")

    threading.Thread(target=_go, daemon=True).start()
    return True
