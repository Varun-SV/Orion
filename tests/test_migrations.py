import sqlite3
import pytest
from orion.store import Store
from orion.config import Config

def test_import_backs_up_and_preserves_all_media(legacy):
    store = Store(legacy)
    backup = store.migrate()
    assert backup.is_file()
    assert store.counts() == {'video': 2, 'music': 1, 'books': 1}
    with sqlite3.connect(backup) as old:
        assert old.execute('PRAGMA user_version').fetchone()[0] == 0
        assert old.execute('SELECT COUNT(*) FROM scan_items').fetchone()[0] == 2
    with store.transaction() as conn:
        assert conn.execute("SELECT value FROM orion_settings WHERE key='theme'").fetchone()[0] == 'clay'
        assert conn.execute('SELECT COUNT(*) FROM orion_destinations').fetchone()[0] == 1
        assert conn.execute("SELECT dest_subpath FROM orion_categories WHERE name='Movies'").fetchone()[0] == 'Films'
        assert 'never-export-me' not in str([tuple(r) for r in conn.execute('SELECT * FROM orion_settings')])
    assert store.migrate() is None

def test_failed_upgrade_leaves_legacy_usable(legacy, monkeypatch):
    store = Store(legacy)
    def broken(conn):
        conn.execute('CREATE TABLE should_rollback(id)')
        raise RuntimeError('migration failed')
    monkeypatch.setattr(store, '_upgrade', broken)
    with pytest.raises(RuntimeError):
        store.migrate()
    with sqlite3.connect(legacy) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM scan_items').fetchone()[0] == 2
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name='should_rollback'").fetchone()
    assert list(legacy.parent.glob('organizer.db.backup-*'))

def test_transaction_rolls_back_and_connections_close(tmp_path):
    store = Store(tmp_path / 'new.db')
    assert store.migrate() is None
    with pytest.raises(ValueError), store.transaction() as conn:
        conn.execute("INSERT INTO orion_settings VALUES('theme','night')")
        raise ValueError('abort')
    with store.transaction() as conn:
        assert not conn.execute("SELECT 1 FROM orion_settings WHERE key='theme'").fetchone()
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'

def test_isolated_config_retains_prefs_without_plaintext_secrets(tmp_path):
    (tmp_path / 'prefs.json').write_text('{"theme":"clay"}')
    cfg = Config(tmp_path)
    assert cfg.db_path == tmp_path / 'organizer.db'
    assert cfg.get_pref('theme') == 'clay'
    cfg.set_pref('theme', 'night')
    assert Config(tmp_path).get_pref('theme') == 'night'
    with pytest.raises(ValueError):
        cfg.set_pref('api_key', 'secret')
