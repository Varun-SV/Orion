import json
import sqlite3
from pathlib import Path
import pytest
from core.database import Database

@pytest.fixture
def legacy(tmp_path):
    path = tmp_path / 'organizer.db'
    db = Database(path)
    db.open()
    a = db.add_source_folder(str(tmp_path / 'a'))
    b = db.add_source_folder(str(tmp_path / 'b'))
    c = db._c()
    for source, folder in [(a, 'a'), (b, 'b')]:
        c.execute('INSERT INTO scan_items(source_folder_id,path,name,item_type,detected_category) VALUES(?,?,?,?,?)',
                  (source, str(tmp_path / folder / 'Arrival.mkv'), 'Arrival.mkv', 'file', 'Movies'))
    c.execute("INSERT INTO rename_choices(original_name,chosen_name) VALUES('Arrival.mkv','Arrival (2016)')")
    c.execute('INSERT INTO music_items(source_path,filename,title,artist) VALUES(?,?,?,?)',
              (str(tmp_path / 'a' / 'track.flac'), 'track.flac', 'First', 'Artist'))
    c.execute('INSERT INTO book_items(source_path,filename,title,author) VALUES(?,?,?,?)',
              (str(tmp_path / 'a' / 'book.epub'), 'book.epub', 'Book', 'Author'))
    db.setting_set('theme', 'clay')
    db.setting_set('tmdb_api_key', 'never-export-me')
    db.add_category('Movies', 'movie', dest_subpath='Films')
    db.upsert_destination('D:', str(tmp_path / 'library'))
    db.close()
    return path

class QuietContext:
    def cancelled(self):
        return False
    def progress(self, *args, **kwargs):
        pass

@pytest.fixture
def context():
    return QuietContext()

@pytest.fixture
def library(tmp_path):
    from orion.store import Store
    from orion.library import Library
    store = Store(tmp_path / 'test.db')
    store.migrate()
    return Library(store)
