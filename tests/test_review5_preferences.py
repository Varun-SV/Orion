import sqlite3

from fastapi.testclient import TestClient

from orion.app import create_app
from orion.config import Config
from orion.store import Store, item_id


def legacy_settings(database, values):
    with sqlite3.connect(database) as conn:
        conn.executemany('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', values.items())


def test_startup_uses_supported_imported_runtime_preferences(legacy):
    destination = item_id('destination', legacy.parent / 'library')
    legacy_settings(legacy, {
        'theme': 'night', 'view': '"list"', 'fingerprint_enabled': 'true',
        'audd_enabled': '0', 'provider_anime': 'anidb',
        'providers': '{"anime_films":"anilist","books":"openlibrary"}',
        'default_destination': destination,
    })
    with TestClient(create_app(legacy.parent), base_url='http://127.0.0.1:4321') as client:
        settings = client.get('/api/v1/settings').json()
        assert settings['theme'] == 'night'
        assert settings['view'] == 'list'
        assert settings['fingerprint_enabled'] is True
        assert settings['audd_enabled'] is False
        assert settings['providers']['anime'] == 'anidb'
        assert settings['providers']['anime_films'] == 'anilist'
        assert settings['default_destination'] == destination
    assert Config(legacy.parent).get_pref('view') == 'list'
    backups = list(legacy.parent.glob('organizer.db.backup-*'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as conn:
        assert conn.execute("SELECT value FROM settings WHERE key='view'").fetchone()[0] == '"list"'
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 0


def test_existing_preferences_win_and_import_is_idempotent(legacy):
    legacy_settings(legacy, {'theme': 'clay', 'view': 'list', 'audd_enabled': 'true', 'provider_anime': 'anidb'})
    config = Config(legacy.parent)
    config.set_pref('theme', 'night')
    config.set_pref('audd_enabled', False)
    config.set_pref('default_destination', None)
    config.set_pref('provider_anime', 'anilist')
    for _ in range(2):
        with TestClient(create_app(legacy.parent), base_url='http://127.0.0.1:4321') as client:
            settings = client.get('/api/v1/settings').json()
            assert settings['theme'] == 'night'
            assert settings['view'] == 'list'
            assert settings['audd_enabled'] is False
            assert settings['default_destination'] is None
            assert settings['providers']['anime'] == 'anilist'
        if _ == 0:
            first_prefs = (legacy.parent / 'prefs.json').read_bytes()
    assert (legacy.parent / 'prefs.json').read_bytes() == first_prefs
    assert len(list(legacy.parent.glob('organizer.db.backup-*'))) == 1


def test_import_rejects_invalid_unsafe_and_unknown_preferences(legacy):
    legacy_settings(legacy, {
        'theme': 'neon', 'view': '{"mode":"list"}', 'fingerprint_enabled': 'yes',
        'audd_enabled': '2', 'provider_movies': 'openlibrary', 'provider_anime': 'unknown',
        'providers': '{"music":"tmdb","unknown":"tmdb","books":{"api_key":"private"}}',
        'default_destination': 'missing-destination', 'tmdb_api_key': 'private-key',
        'media_server_settings': '{"enabled":true,"url":"https://unsafe.example"}',
        'provider_health_tmdb': '{"health":"connected"}', 'unknown_setting': 'private-value',
    })
    with TestClient(create_app(legacy.parent), base_url='http://127.0.0.1:4321') as client:
        settings = client.get('/api/v1/settings').json()
        assert settings['theme'] == 'ivory'
        assert settings['view'] == 'grid'
        assert settings['fingerprint_enabled'] is False
        assert settings['audd_enabled'] is False
        assert settings['default_destination'] is None
        assert settings['providers']['movies'] == 'tmdb'
        assert settings['providers']['anime'] == 'tmdb'
        assert client.get('/api/v1/server').json()['enabled'] is False
    config = Config(legacy.parent)
    assert config.get_pref('unknown_setting') is None
    assert config.get_pref('provider_health_tmdb') is None
    assert config.get_pref('tmdb_api_key') is None
    if (legacy.parent / 'prefs.json').exists():
        assert 'private' not in (legacy.parent / 'prefs.json').read_text(encoding='utf-8')


def test_already_upgraded_database_still_restores_missing_preferences(legacy):
    assert Store(legacy).migrate() is not None
    assert Config(legacy.parent).get_pref('theme') is None
    with TestClient(create_app(legacy.parent), base_url='http://127.0.0.1:4321') as client:
        assert client.get('/api/v1/settings').json()['theme'] == 'clay'
        assert client.app.state.backup_path is None
    assert Config(legacy.parent).get_pref('theme') == 'clay'
    assert len(list(legacy.parent.glob('organizer.db.backup-*'))) == 1
