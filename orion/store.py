from __future__ import annotations
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from orion.models import KINDS, KIND_NAMES

SCHEMA_VERSION = 1

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def normalized(path):
    return os.path.normcase(os.path.abspath(path))

def item_id(source_id: str, path: Path) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, source_id + ':' + normalized(path)))

def is_secret(key):
    return any(part in key.lower() for part in ('api_key', 'token', 'password', 'secret', 'credential'))

def safe_metadata(value):
    if isinstance(value, dict):
        return {k: safe_metadata(v) for k, v in value.items() if not is_secret(k)}
    if isinstance(value, list):
        return [safe_metadata(v) for v in value]
    return value

class Store:
    def __init__(self, db_path: Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connection(self):
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=30000')
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=FULL')
        return conn

    @contextmanager
    def transaction(self):
        conn = self._connection()
        try:
            conn.execute('BEGIN IMMEDIATE')
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> Path | None:
        existed = self.path.exists() and self.path.stat().st_size > 0
        conn = self._connection()
        backup = None
        try:
            version = conn.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError('Database needs a newer Orion version; use a compatible app or backup.')
            if version == SCHEMA_VERSION:
                return None
            if existed:
                backup = self.path.with_name(self.path.name + '.backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8])
                with sqlite3.connect(backup) as snapshot:
                    conn.backup(snapshot)
            conn.execute('BEGIN IMMEDIATE')
            self._upgrade(conn)
            conn.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
            conn.commit()
            return backup
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _upgrade(self, conn):
        statements = [
            'CREATE TABLE orion_sources(id TEXT PRIMARY KEY,path TEXT UNIQUE NOT NULL,label TEXT NOT NULL,kind TEXT NOT NULL DEFAULT "auto",watch INTEGER NOT NULL DEFAULT 0)',
            'CREATE TABLE orion_destinations(id TEXT PRIMARY KEY,path TEXT UNIQUE NOT NULL,label TEXT NOT NULL)',
            'CREATE TABLE orion_categories(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,api_pref TEXT NOT NULL,dest_subpath TEXT NOT NULL,settings TEXT NOT NULL DEFAULT "{}")',
            'CREATE TABLE orion_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)',
            'CREATE TABLE orion_items(id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES orion_sources(id),path TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,signature TEXT NOT NULL,metadata TEXT NOT NULL,decision TEXT,updated_at TEXT NOT NULL,UNIQUE(source_id,path))',
            'CREATE INDEX orion_items_filter ON orion_items(kind,status)',
            'CREATE TABLE orion_plans(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL)',
            'CREATE TABLE orion_operations(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL REFERENCES orion_plans(id),data TEXT NOT NULL,updated_at TEXT NOT NULL)',
            'CREATE TABLE orion_batches(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,state TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL)',
            'CREATE TABLE orion_jobs(id TEXT PRIMARY KEY,kind TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,progress TEXT NOT NULL DEFAULT "{}",result TEXT,error TEXT,cancel INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)',
            'CREATE TABLE orion_activity(id INTEGER PRIMARY KEY,action TEXT NOT NULL,detail TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL)',
            'CREATE TABLE orion_profiles(id TEXT PRIMARY KEY,kind TEXT NOT NULL,data TEXT NOT NULL)',
        ]
        for statement in statements:
            conn.execute(statement)
        self._import_legacy(conn)
        for kind in KINDS:
            conn.execute('INSERT OR IGNORE INTO orion_categories VALUES(?,?,?,?,?,?)',
                         (kind, KIND_NAMES[kind], kind, 'musicbrainz' if kind == 'music' else 'openlibrary' if kind == 'books' else 'tmdb', KIND_NAMES[kind], '{}'))

    def _import_legacy(self, conn):
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def rows(name):
            return [dict(r) for r in conn.execute(f'SELECT * FROM {name}')] if name in tables else []
        source_map = {}
        for source in rows('source_folders'):
            sid = item_id('source', source['path'])
            source_map[source['id']] = sid
            conn.execute('INSERT INTO orion_sources(id,path,label) VALUES(?,?,?)', (sid, source['path'], source.get('tag') or Path(source['path']).name))
        for dest in rows('destination_roots'):
            conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)', (item_id('destination', dest['path']), dest['path'], dest.get('drive', 'Library')))
        for setting in rows('settings'):
            if not is_secret(setting['key']):
                conn.execute('INSERT INTO orion_settings VALUES(?,?)', (setting['key'], setting['value']))
        def kind_for(name):
            text = name.lower().replace(' ', '_')
            return {'movie':'movies','tv':'series','anime_movie':'anime_films','webseries':'web_series','book':'books'}.get(text, text if text in KINDS else 'movies')
        for cat in rows('categories'):
            kind = kind_for(cat.get('name', cat.get('media_type', 'movies')))
            conn.execute('INSERT INTO orion_categories VALUES(?,?,?,?,?,?)', (str(cat['id']),cat['name'],kind,cat.get('api_pref','tmdb'),cat.get('dest_subpath',''),json.dumps(safe_metadata(cat))))
        videos = rows('scan_items')
        file_choices = {normalized(r['original_path']): r for r in rows('file_rename_choices')}
        choices = {r['original_name']: r for r in rows('rename_choices')}
        counts = {}
        for row in videos:
            counts[row['name']] = counts.get(row['name'], 0) + 1
        def source_for(path, old_id=None):
            if old_id in source_map:
                return source_map[old_id]
            matched = [(r['path'], r['id']) for r in conn.execute('SELECT * FROM orion_sources')
                       if normalized(path).startswith(normalized(r['path']) + os.sep)]
            if matched:
                return max(matched, key=lambda r: len(r[0]))[1]
            root = str(Path(path).parent)
            sid = item_id('source', root)
            conn.execute('INSERT OR IGNORE INTO orion_sources(id,path,label) VALUES(?,?,?)', (sid,root,Path(root).name))
            return sid
        def insert(row, path, kind, metadata, choice=None, old_id=None):
            sid = source_for(path, old_id)
            iid = item_id(sid, path)
            decision = None
            status = row.get('status', 'pending')
            if status not in ('pending','error','unavailable','no_match'):
                status = 'pending'
            if choice:
                decision = {'item_id':iid,'provider':choice.get('source','legacy'),'provider_id':'','metadata':safe_metadata(choice),'evidence':['Imported unambiguous legacy decision']}
                status = 'approved'
            conn.execute('INSERT OR IGNORE INTO orion_items VALUES(?,?,?,?,?,?,?,?,?)',
                         (iid,sid,path,kind,status,'{}',json.dumps(safe_metadata(metadata)),json.dumps(decision) if decision else None,utcnow()))
        for row in videos:
            if not row.get('is_leaf', 1):
                continue
            choice = choices.get(row['name']) if counts[row['name']] == 1 else None
            if choice:
                choice = {**choice,'title':choice['chosen_name']}
            explicit = file_choices.get(normalized(row['path']))
            if explicit:
                choice = {**(choice or {}), **explicit, 'filename':explicit['chosen_name'], 'title':(choice or {}).get('title', row['name'])}
            insert(row,row['path'],kind_for(row.get('detected_category','movies')),{'title':row['name']},choice,row.get('source_folder_id'))
        for table, choice_table, kind in [('music_items','music_rename_choices','music'),('book_items','book_rename_choices','books')]:
            saved = {r['source_path']:r for r in rows(choice_table)}
            for row in rows(table):
                insert(row,row['source_path'],kind,row,saved.get(row['source_path']))
        for row in rows('activity_log'):
            conn.execute('INSERT INTO orion_activity(action,detail,status,created_at) VALUES(?,?,?,?)',
                         (row['action'], json.dumps({'legacy_id':row['id'],'summary':'Legacy activity imported. Free-form details remain in the original tables and migration backup.'}), row['status'],row['created_at']))

    def counts(self):
        result = {'video':0,'music':0,'books':0}
        with self.transaction() as conn:
            for row in conn.execute('SELECT kind,COUNT(*) AS n FROM orion_items GROUP BY kind'):
                result[row['kind'] if row['kind'] in ('music','books') else 'video'] += row['n']
        return result
