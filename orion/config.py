from __future__ import annotations
import json
import os
from pathlib import Path
from threading import RLock
from orion.store import is_secret

class Config:
    def __init__(self, data_dir: Path | None = None):
        self.app_data_dir = Path(data_dir) if data_dir else Path(os.environ.get('APPDATA', Path.home())) / 'Orion'
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.app_data_dir / 'organizer.db'
        self._prefs_path = self.app_data_dir / 'prefs.json'
        self._lock = RLock()
        self._keys = {}
        self._session_services = set()
        try:
            self._prefs = json.loads(self._prefs_path.read_text(encoding='utf-8-sig'))
        except FileNotFoundError:
            self._prefs = {}
        except (ValueError, OSError) as exc:
            raise RuntimeError('Cannot read preferences; preserve prefs.json and restore a backup.') from exc

    def get_pref(self, key, default=None):
        return self._prefs.get(key, default)

    def set_pref(self, key, value):
        if is_secret(key):
            raise ValueError('Store credentials through the keychain, never preferences.')
        with self._lock:
            updated = {**self._prefs, key:value}
            temp = self._prefs_path.with_suffix('.json.tmp')
            temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, self._prefs_path)
            self._prefs = updated

    def get_api_key(self, service):
        if service not in self._keys:
            try:
                import keyring
                self._keys[service] = keyring.get_password('Orion', service) or ''
            except Exception:
                self._keys[service] = ''
        return self._keys[service]

    def set_api_key(self, service, key, session_only=False):
        key = key.strip()
        if session_only:
            self._session_services.add(service)
        else:
            try:
                import keyring
                if key:
                    keyring.set_password('Orion', service, key)
                else:
                    try:
                        keyring.delete_password('Orion', service)
                    except keyring.errors.PasswordDeleteError:
                        pass
            except Exception as exc:
                raise ValueError('Secure credential storage unavailable. Choose session-only explicitly.') from exc
            self._session_services.discard(service)
        self._keys[service] = key
        return {'configured':bool(key),'storage':'session' if session_only else 'keychain'}
