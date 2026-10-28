import json
from orion.store import Store, item_id

def test_ambiguous_names_never_share_decisions(legacy):
    store = Store(legacy)
    store.migrate()
    with store.transaction() as conn:
        rows = conn.execute("SELECT id,decision,status FROM orion_items WHERE kind='movies'").fetchall()
        assert len({r['id'] for r in rows}) == 2
        assert all(r['decision'] is None for r in rows)
        assert all(r['status'] == 'pending' for r in rows)

def test_unique_name_choice_is_imported_only_for_one_item(legacy):
    import sqlite3
    with sqlite3.connect(legacy) as conn:
        conn.execute('DELETE FROM scan_items WHERE source_folder_id=2')
    store = Store(legacy)
    store.migrate()
    with store.transaction() as conn:
        row = conn.execute("SELECT decision,status FROM orion_items WHERE kind='movies'").fetchone()
        assert json.loads(row['decision'])['metadata']['title'] == 'Arrival (2016)'
        assert row['status'] == 'approved'

def test_identity_is_source_scoped_and_stable(tmp_path):
    assert item_id('a', tmp_path / 'film.mkv') != item_id('b', tmp_path / 'film.mkv')
    assert item_id('a', tmp_path / '.' / 'film.mkv') == item_id('a', tmp_path / 'film.mkv')

def test_path_specific_video_choice_survives_import(legacy):
    import sqlite3
    path = str(legacy.parent / 'a' / 'Arrival.mkv')
    with sqlite3.connect(legacy) as conn:
        conn.execute('INSERT INTO file_rename_choices(original_path,chosen_name) VALUES(?,?)', (path, 'Arrival - theatrical.mkv'))
    store = Store(legacy)
    store.migrate()
    with store.transaction() as conn:
        row = conn.execute('SELECT decision FROM orion_items WHERE path=?', (path,)).fetchone()
        assert json.loads(row['decision'])['metadata']['filename'] == 'Arrival - theatrical.mkv'
        other = conn.execute('SELECT decision FROM orion_items WHERE path<>? AND kind="movies"', (path,)).fetchone()
        assert other['decision'] is None
