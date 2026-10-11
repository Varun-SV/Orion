"""Focused regressions for the latest Orion PR #3 review comments."""
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from orion.config import Config
from orion.discovery import Discovery
from orion.executor import Executor
from orion.integrations.manager import ServerIntegration, ServerSettings
from orion.integrations.server import MediaServerClient, ServerError, ServerInfo
from orion.library import Library
from orion.models import MatchDecision
from orion.planner import Planner, PlanOptions
from orion.providers import ProviderError, Providers
from orion.store import Store, item_id
from tests_support import make_plan


def test_legacy_root_source_owns_its_music_and_books(legacy):
    root = str(legacy.parent.anchor)
    with sqlite3.connect(legacy) as conn:
        conn.execute("UPDATE source_folders SET path=? WHERE path=?", (root, str(legacy.parent / 'a')))
    store = Store(legacy)
    store.migrate()
    library = Library(store)
    expected = item_id('source', root)
    assert library.query(kind='music').items[0].source_id == expected
    assert library.query(kind='books').items[0].source_id == expected
    assert not any(row['path'] == str(legacy.parent / 'a') for row in library.sources())


@pytest.mark.parametrize('failure_state', ['error', 'no_match'])
def test_successful_lookup_retry_resets_only_failure_state(library, tmp_path, context, failure_state):
    root = tmp_path / 'music'
    root.mkdir()
    (root / 'track.mp3').write_bytes(b'fixture audio')
    sid = library.add_source(root, kind='music')['id']
    Discovery(library).scan([sid], False, context)
    item = library.query().items[0]
    if failure_state == 'error':
        library.lookup_failed(item.id, item.signature, 'provider_unavailable')
    else:
        library.publish_lookup(item.id, item.signature, [])
    assert library.get(item.id).status == failure_state
    assert library.publish_lookup(item.id, item.signature, [{'title': 'Found'}])
    updated = library.get(item.id)
    assert updated.status == 'pending'
    assert updated.metadata['lookup_state'] == 'ready'


@pytest.mark.parametrize('deep', [False, True])
def test_returning_inplace_item_remains_organised(library, tmp_path, context, deep):
    root = tmp_path / 'music'
    root.mkdir()
    original = root / 'track.mp3'
    original.write_bytes(b'fixture audio')
    sid = library.add_source(root, kind='music')['id']
    scanner = Discovery(library)
    scanner.scan([sid], False, context)
    item = library.query().items[0]
    library.decide(item.id, MatchDecision(item_id=item.id, metadata={
        'title': 'Renamed Track', 'artist': 'Artist', 'album': 'Album'}))
    planner = Planner(library)
    plan = planner.create([item.id], PlanOptions(in_place=True))
    assert plan.operations and not plan.issues
    assert Executor(library, planner).execute(plan.id, 1, context).state == 'completed'
    organised = library.get(item.id)
    assert organised.status == 'organised'
    assert Path(organised.path).exists()
    library.status(item.id, 'unavailable')
    scanner.scan([sid], deep, context)
    assert library.get(item.id).status == 'organised'
    assert library.get(item.id).path == organised.path


def test_late_forward_directory_arrival_is_partial_and_not_lost(library, tmp_path, context):
    planner, plan, source, target = make_plan(library, tmp_path, context, directory=True)
    item_id = plan.operations[0].item_id
    original_decision = library.get(item_id).decision
    extra = source.parent / 'late.txt'

    class InjectArrival(Executor):
        injected = False

        def _journal(self, operation, state, **details):
            super()._journal(operation, state, **details)
            if state == 'completed' and operation.kind == 'move' and not self.injected:
                self.injected = True
                extra.write_bytes(b'new arrival must stay')

    result = InjectArrival(library, planner).execute(plan.id, 1, context)
    assert result.state == 'partial'
    assert item_id in result.recovery_item_ids
    assert target.read_bytes() == b'original media bytes'
    assert extra.read_bytes() == b'new arrival must stay'
    recovered = library.get(item_id)
    assert recovered.status == 'error' and recovered.decision == original_decision
    assert str(source.parent) in recovered.metadata['recovery_paths']
    Discovery(library).scan([recovered.source_id], False, context)
    assert library.get(item_id).status == 'error'
    assert library.get(item_id).decision == original_decision


@pytest.mark.parametrize('replacement', ['changed', 'symlink'])
def test_audd_cannot_read_replaced_scanned_file(library, tmp_path, context, replacement):
    root = tmp_path / 'audio'
    root.mkdir()
    media = root / 'track.mp3'
    media.write_bytes(b'original sample')
    sid = library.add_source(root, kind='music')['id']
    Discovery(library).scan([sid], False, context)
    item = library.query().items[0]
    cfg = Config(tmp_path / 'preferences')
    cfg.set_pref('audd_enabled', True)
    cfg.set_api_key('audd', 'fixture-key', session_only=True)
    uploaded = []
    def transport(provider, method, url, ctx, **kwargs):
        uploaded.append(kwargs['files']['file'][1])
        return {'status': 'success', 'result': {'title': 'Track', 'song_link': 'fixture'}}
    provider = Providers(cfg, request=transport, store=library.store)
    if replacement == 'changed':
        media.write_bytes(b'different sample of another length')
    else:
        media.unlink()
        outside = tmp_path / 'private.mp3'
        outside.write_bytes(b'private never upload')
        try:
            media.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip('Cannot create symlinks on this host')
    with pytest.raises(ProviderError) as error:
        provider.candidates(item, context, provider='audd')
    assert error.value.code == 'item_changed'
    assert uploaded == []


@pytest.mark.parametrize('failure', [False, True])
def test_stale_server_test_does_not_publish_old_health(library, tmp_path, context, monkeypatch, failure):
    runtime = SimpleNamespace(store=library.store, config=Config(tmp_path / 'preferences'), providers=None)
    server = ServerIntegration(runtime)
    first = ServerSettings(enabled=True, url='http://127.0.0.1:8096', user_id='old')
    server.save(first)
    runtime.config.set_api_key('media_server', 'fixture', session_only=True)
    payload = {'server_revision': server.revision()}

    def test_connection(client, ctx):
        server.save(first.model_copy(update={'user_id': 'new'}))
        if failure:
            raise ServerError('server_unavailable')
        return ServerInfo(id='old-server', name='Old server', version='1.0')

    monkeypatch.setattr(MediaServerClient, 'test_connection', test_connection)
    monkeypatch.setattr(MediaServerClient, 'users', lambda self, ctx: [])
    with pytest.raises(ServerError):
        server.run('server_test', payload, context)
    assert server.status()['health'] == 'not_checked'
    assert server.configuration().user_id == 'new'
