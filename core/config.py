"""
App config — paths, first-launch detection, OS-keychain API key storage.
API keys are stored in the OS keychain (Windows Credential Manager, macOS
Keychain, Linux Secret Service via libsecret). They persist until the user
explicitly clears them from Settings → API Keys.
Falls back to session-only storage if no keyring backend is available.
"""
from __future__ import annotations
import os, json
from pathlib import Path

try:
    import keyring
    import keyring.errors
    _KEYRING_OK = True
except Exception:
    _KEYRING_OK = False

_KR_SERVICE = "Orion"


class Config:
    APP_NAME = "Orion"

    def __init__(self) -> None:
        self._appdata = Path(os.environ.get("APPDATA", Path.home())) / self.APP_NAME
        self._appdata.mkdir(parents=True, exist_ok=True)
        self._api_keys: dict[str, str] = {}
        self._prefs_path = self._appdata / "prefs.json"
        self._prefs: dict = self._load_prefs()

    @property
    def app_data_dir(self) -> Path:
        return self._appdata

    @property
    def db_path(self) -> Path:
        return self._appdata / "organizer.db"

    def is_first_launch(self) -> bool:
        return not self.db_path.exists()

    def mark_launched(self) -> None:
        self._set("launched", True)

    # ── API keys — OS keychain with in-memory cache ──────────────────────
    def set_api_key(self, service: str, key: str) -> None:
        key = key.strip()
        self._api_keys[service] = key
        if _KEYRING_OK:
            try:
                if key:
                    keyring.set_password(_KR_SERVICE, service, key)
                else:
                    keyring.delete_password(_KR_SERVICE, service)
            except Exception:
                pass

    def get_api_key(self, service: str) -> str:
        if service not in self._api_keys:
            if _KEYRING_OK:
                try:
                    val = keyring.get_password(_KR_SERVICE, service) or ""
                    self._api_keys[service] = val
                except Exception:
                    self._api_keys[service] = ""
            else:
                self._api_keys[service] = ""
        return self._api_keys.get(service, "")

    def has_api_key(self, service: str) -> bool:
        return bool(self.get_api_key(service))

    def delete_api_key(self, service: str) -> None:
        """Remove key from memory and OS keychain."""
        self._api_keys.pop(service, None)
        if _KEYRING_OK:
            try:
                keyring.delete_password(_KR_SERVICE, service)
            except Exception:
                pass

    @staticmethod
    def keyring_available() -> bool:
        return _KEYRING_OK

    # ── UI prefs (geometry, last panel index…) ───────────────────────────
    def save_geometry(self, key: str, data: dict) -> None:
        self._set(f"geo_{key}", data)

    def load_geometry(self, key: str) -> dict | None:
        return self._prefs.get(f"geo_{key}")

    def get_pref(self, key: str, default=None):
        return self._prefs.get(key, default)

    def set_pref(self, key: str, value) -> None:
        self._set(key, value)

    def _load_prefs(self) -> dict:
        if self._prefs_path.exists():
            try:
                return json.loads(self._prefs_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _set(self, key: str, value) -> None:
        self._prefs[key] = value
        self._prefs_path.write_text(
            json.dumps(self._prefs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
