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

    def import_preferences(self, store):
        """Restore supported imported settings without replacing saved preferences."""
        from orion.models import KINDS
        from orion.providers import compatible_providers
        with store.transaction() as conn:
            imported = dict(conn.execute('SELECT key,value FROM orion_settings'))
            destinations = {row[0] for row in conn.execute('SELECT id FROM orion_destinations')}
        decoded = {}
        for key, raw in imported.items():
            if is_secret(key):
                continue
            try:
                decoded[key] = json.loads(raw)
            except (ValueError, TypeError):
                decoded[key] = raw
        candidates = {}
        for key, choices in [('theme', ('ivory', 'clay', 'night')), ('view', ('grid', 'list'))]:
            value = decoded.get(key)
            if isinstance(value, str) and value in choices:
                candidates[key] = value
        for key in ('fingerprint_enabled', 'audd_enabled'):
            value = decoded.get(key)
            if isinstance(value, bool) or type(value) is int and value in (0, 1):
                candidates[key] = bool(value)
        providers = decoded.get('providers', {})
        for kind in KINDS:
            key = 'provider_' + kind
            value = decoded.get(key, providers.get(kind) if isinstance(providers, dict) else None)
            if isinstance(value, str) and value in compatible_providers(kind):
                candidates[key] = value
        destination = decoded.get('default_destination')
        if isinstance(destination, str) and destination in destinations:
            candidates['default_destination'] = destination
        with self._lock:
            for key, value in candidates.items():
                if key not in self._prefs:
                    self.set_pref(key, value)

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
            if service not in self._session_services:
                try:
                    import keyring
                    try:
                        persisted = keyring.get_password('Orion', service)
                    except keyring.errors.NoKeyringError:
                        # A fresh session key works without an OS vault, but a
                        # known saved key must be removed before changing modes.
                        if self._keys.get(service):
                            raise
                        persisted = None
                    if persisted:
                        keyring.delete_password('Orion', service)
                except Exception as exc:
                    raise ValueError('Cannot remove saved credential. Restore secure credential storage before choosing session-only.') from exc
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
