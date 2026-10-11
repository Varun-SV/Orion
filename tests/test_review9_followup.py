"""Regressions for Orion PR #3: credential races, watch durability, linked roots."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orion.config import Config
from orion.discovery import Cancelled, Discovery
from orion.integrations.manager import ServerIntegration, ServerSettings
from orion.integrations.server import MediaServerClient, ServerError, ServerInfo
from orion.providers import ProviderError
from orion.routes.settings import archive_source, resume_source
from orion.services import Services
from orion.watcher import Watcher


@pytest.mark.parametrize('outcome', ['success', 'failure', 'cancelled'])
def test_provider_test_never_publishes_stale_or_cancelled_health(tmp_path, library, context, outcome):
    cfg = Config(tmp_path / 'provider-prefs')
    cfg.set_api_key('tmdb', 'first', session_only=True)
    previous = cfg.key_revision('tmdb')
    cfg.set_pref('provider_health_tmdb', {'health': 'not_checked'})
    cancellation = [False]

    def call(*args, **kwargs):
        if outcome == 'cancelled':
            cancellation[0] = True
        else:
            with cfg._lock:
                cfg.set_api_key('tmdb', 'replacement', session_only=True)
                cfg.set_pref('provider_health_tmdb', {'health': 'not_checked'})
        if outcome == 'failure':
            raise ProviderError('provider_unavailable', 'tmdb')
        return {}

    ctx = SimpleNamespace(cancelled=lambda: cancellation[0])
    provider = SimpleNamespace(_call=call, _key=cfg.get_api_key)
    services = Services(cfg, library.store, library, None, provider, None, None)
    with pytest.raises(Cancelled if outcome == 'cancelled' else ProviderError) as exc:
        services.test_provider({'provider': 'tmdb', 'provider_revision': previous}, ctx)
    if outcome != 'cancelled':
        assert exc.value.code == 'provider_configuration_changed'
    assert cfg.get_pref('provider_health_tmdb')['health'] == 'not_checked'


def test_provider_test_old_queued_generation_fails_without_connecting(library, tmp_path, context):
    cfg = Config(tmp_path / 'provider')
    old = cfg.key_revision('tmdb')
    cfg.set_api_key('tmdb', 'replacement', session_only=True)
    provider = SimpleNamespace(_call=lambda *a, **k: pytest.fail('stale test performed network request'))
    services = Services(cfg, library.store, library, None, provider, None, None)
    with pytest.raises(ProviderError) as exc:
        services.test_provider({'provider':'tmdb','provider_revision':old},context)
    assert exc.value.code == 'provider_configuration_changed'


@pytest.mark.parametrize('outcome', ['success', 'failure'])
def test_server_health_ignores_changed_or_cleared_credentials(library, tmp_path, context, monkeypatch, outcome):
    cfg = Config(tmp_path / 'server-prefs')
    runtime = SimpleNamespace(config=cfg, store=library.store, providers=None)
    server = ServerIntegration(runtime)
    server.save(ServerSettings(enabled=True,url='http://127.0.0.1:8096'))
    cfg.set_api_key('media_server', 'first', session_only=True)
    payload = {'server_revision':server.revision()}
    def test_connection(client,ctx):
        with cfg._lock:
            cfg.set_api_key('media_server', '', session_only=True)
            cfg.set_pref('server_health', {'health':'not_checked','detail':''})
        if outcome == 'failure':
            raise ServerError('server_unavailable')
        return ServerInfo(id='old',name='Old',version='1.0')
    monkeypatch.setattr(MediaServerClient,'test_connection',test_connection)
    monkeypatch.setattr(MediaServerClient,'users',lambda self,ctx:[])
    with pytest.raises(ServerError):
        server.run('server_test',payload,context)
    assert server.status()['health'] == 'not_checked'
    assert server.revision() != payload['server_revision']
    assert cfg.get_api_key('media_server') == ''


def test_watcher_uses_small_digest_for_jobs_and_checkpoints(library, tmp_path, context):
    root=tmp_path / 'watched'
    root.mkdir()
    for index in range(300):
        (root / f'{index:05}.mkv').write_bytes(b'movie')
    sid=library.add_source(root, kind='movies')['id']
    watcher=Watcher(library,Discovery(library),clock=lambda:1000)
    class Queue:
        def __init__(self): self.payloads=[]
        def submit(self,kind,payload):
            assert kind == 'watch_scan'
            self.payloads.append(payload)
            return SimpleNamespace(id='queued')
        def get(self,job_id):return SimpleNamespace(state='running')
    queue=Queue()
    watcher.jobs=queue
    watcher.configure(sid,enabled=True,stability_seconds=5)
    first=watcher.snapshot(root,context)
    assert first['count'] == 300 and len(json.dumps(first)) < 150
    watcher.tick(context)
    watcher.clock=lambda:1006
    assert watcher.tick(context).queued == 1
    assert len(json.dumps(queue.payloads[0])) < 220
    assert len(json.dumps(watcher._load(sid))) < 500
    assert watcher.scan_ready(queue.payloads[0],context).processed == 300
    (root/'00001.mkv').write_bytes(b'modified')
    assert watcher.snapshot(root,context)['digest'] != first['digest']
    skipped=watcher.scan_ready(queue.payloads[0],context)
    assert skipped['skipped'] is True and skipped['reason'] == 'source_changed'


def test_resume_rejects_linked_ancestor(library, tmp_path):
    parent=tmp_path / 'source-parent'
    root=parent / 'movies'
    root.mkdir(parents=True)
    sid=library.add_source(root,kind='movies')['id']
    runtime=SimpleNamespace(library=library,store=library.store)
    archive_source(sid,runtime)
    renamed=tmp_path / 'actual-parent'
    parent.rename(renamed)
    try:
        parent.symlink_to(renamed,target_is_directory=True)
    except (OSError,NotImplementedError):
        pytest.skip('Symlink creation unavailable')
    with pytest.raises(ValueError,match='Reconnect'):
        resume_source(sid,runtime)
    with library.store.transaction() as conn:
        archived=conn.execute('SELECT value FROM orion_settings WHERE key=?',
                              ('source_archived_'+sid,)).fetchone()
    assert archived[0] == 'true'
