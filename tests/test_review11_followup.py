"""Regression tests for the subsequent Orion PR #3 review round."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from orion.config import Config
from orion.discovery import Cancelled, Discovery, signature
from orion.integrations.manager import ServerIntegration, ServerSettings
from orion.integrations.server import MediaServerClient, ServerError
from orion.jobs import JobManager
from orion.library import Library
from orion.models import MediaItem, MatchDecision
from orion.providers import Providers, ProviderError
from tests_support import make_plan


@pytest.mark.parametrize('failure', [False, True])
def test_cancelled_server_hints_never_publish(library,tmp_path,context,monkeypatch,failure):
    cfg=Config(tmp_path/'prefs')
    runtime=SimpleNamespace(store=library.store,config=cfg,providers=None,library=library)
    server=ServerIntegration(runtime)
    server.save(ServerSettings(enabled=True,url='http://127.0.0.1:8096'))
    cfg.set_api_key('media_server','key',session_only=True)
    root=tmp_path/'input';root.mkdir()
    media=root/'film.mkv';media.write_bytes(b'fixture')
    sid=library.add_source(root,kind='movies')['id']
    Discovery(library).scan([sid],False,context)
    item=library.query().items[0]
    cancelled=[False]
    def items(*args,**kwargs):
        cancelled[0]=True
        if failure:raise ServerError('server_unavailable')
        return []
    monkeypatch.setattr(MediaServerClient,'items',items)
    ctx=SimpleNamespace(cancelled=lambda:cancelled[0])
    with pytest.raises(ServerError):
        server.run('server_hints',{'server_revision':server.revision(),'item_id':item.id},ctx)
    assert server.saved_hints(item.id)['state']=='not_checked'


def test_cancelled_episode_mapping_is_not_stored(library,tmp_path,context,monkeypatch):
    from orion.gaps import EpisodeGaps
    cfg=Config(tmp_path/'prefs')
    runtime=SimpleNamespace(store=library.store,config=cfg,providers=None,library=library)
    server=ServerIntegration(runtime)
    server.save(ServerSettings(enabled=True,url='http://127.0.0.1:8096'))
    cfg.set_api_key('media_server','key',session_only=True)
    cancelled=[False]
    def compare(*args,**kwargs):
        cancelled[0]=True
        return SimpleNamespace(state='ready')
    monkeypatch.setattr(EpisodeGaps,'compare',compare)
    ctx=SimpleNamespace(cancelled=lambda:cancelled[0])
    with pytest.raises(ServerError):
        server.run('episode_gaps',{'server_revision':server.revision(),'series_id':'show',
              'mapping':{'provider_id':'123','confirmed':True}},ctx)
    with library.store.transaction() as conn:
        assert not conn.execute("SELECT 1 FROM orion_settings WHERE key LIKE 'server_mapping_%'").fetchone()


def test_retry_revisions_are_refreshed_for_explicit_retries(library,tmp_path):
    cfg=Config(tmp_path/'prefs')
    cfg.set_api_key('tmdb','key',session_only=True)
    runtime=SimpleNamespace(config=cfg)
    runtime.server=SimpleNamespace(revision=lambda:'current-server')
    manager=JobManager(library.store,{'provider_test':lambda p,c:{'ok':True},
                       'server_test':lambda p,c:{'ok':True}},runtime=runtime)
    try:
        from orion.store import utcnow
        with library.store.transaction() as conn:
            for ident,kind,payload in [('p','provider_test',{'provider':'tmdb','provider_revision':'old'}),
                                        ('s','server_test',{'server_revision':'old'})]:
                conn.execute('INSERT INTO orion_jobs(id,kind,state,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                            (ident,kind,'interrupted',json.dumps(payload),utcnow(),utcnow()))
        manager.retry('p')
        manager.retry('s')
        with library.store.transaction() as conn:
            p=json.loads(conn.execute("SELECT payload FROM orion_jobs WHERE id='p'").fetchone()[0])
            s=json.loads(conn.execute("SELECT payload FROM orion_jobs WHERE id='s'").fetchone()[0])
        assert p['provider_revision']==cfg.key_revision('tmdb')
        assert s['server_revision']=='current-server'
    finally:
        manager.shutdown()


@pytest.mark.parametrize('body_size',[5000, 4*1024*1024+1])
def test_metadata_http_rejects_oversized_response(monkeypatch,context,body_size):
    class Response:
        status_code=200
        headers={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,chunk_size=65536):
            for offset in range(0,body_size,chunk_size):
                yield b'X'*min(chunk_size,body_size-offset)
    monkeypatch.setattr(requests,'request',lambda *a,**kw:Response())
    import orion.providers as provider
    monkeypatch.setattr(provider,'MAX_PROVIDER_RESPONSE',4096 if body_size==5000 else 4*1024*1024)
    with pytest.raises(ProviderError,match='response too large'):
        Providers._request('tmdb','GET','https://invalid.example',context)


def test_directory_signature_rejects_walk_failure(tmp_path,monkeypatch):
    import orion.discovery as discovery
    root=tmp_path/'media';root.mkdir()
    (root/'file.mkv').write_bytes(b'fixture')
    original=discovery.os.walk
    def incomplete(path,*,followlinks=False,onerror=None):
        if Path(path)==root:
            yield str(root),[],['file.mkv']
            if onerror:onerror(PermissionError('Nested directory unreadable'))
        else:
            yield from original(path,followlinks=followlinks,onerror=onerror)
    monkeypatch.setattr(discovery.os,'walk',incomplete)
    with pytest.raises(OSError,match='Incomplete directory'):
        signature(root)


def test_case_only_rediscovery_preserves_approval(library,tmp_path,context,monkeypatch):
    import orion.library as module
    root=tmp_path/'music';root.mkdir()
    old=root/'track.flac';old.write_bytes(b'audio')
    sid=library.add_source(root,kind='music')['id']
    item=MediaItem(id='fixed',source_id=sid,path=str(old),kind='music',signature=signature(old))
    library.upsert(item)
    library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Song'}))
    new=root/'Track.flac'
    old.rename(new)
    # Linux normally case-folds differently, model Win32 normcase here.
    monkeypatch.setattr(module,'normalized',lambda p: str(p).lower())
    returned=library.discovered(item.model_copy(update={'path':str(new)}))
    assert returned.id == item.id
    updated=library.get(item.id)
    assert updated.path==str(new) and updated.decision.metadata['title']=='Song'
    assert library.query().total==1


def test_prepublication_failure_without_recovery_artifacts_is_not_actionable():
    # No destination, staged file, remove intent, or partial copy means a
    # terminal error journal has nothing safe to resume.
    sql="""SELECT 1 FROM orion_operations WHERE json_extract(data,'$.state') IN
    ('intent','staged','copied','finalised','cancelled') OR
    (json_extract(data,'$.state')='error' AND
    (json_extract(data,'$.verification.final_signature') IS NOT NULL OR
    json_extract(data,'$.verification.temp_path') IS NOT NULL OR
    json_extract(data,'$.verification.remove_intent')=1 OR
    json_extract(data,'$.verification.partial_sha256') IS NOT NULL))"""
    import sqlite3
    conn=sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE orion_operations(data TEXT)')
    conn.execute('INSERT INTO orion_operations VALUES(?)',(json.dumps({'state':'error','verification':{}}),))
    assert conn.execute(sql).fetchone() is None
    conn.close()
