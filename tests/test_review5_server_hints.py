import hashlib
import json
from types import SimpleNamespace

import pytest

from orion.config import Config
from orion.discovery import Discovery
from orion.integrations.manager import ServerIntegration, ServerSettings
from orion.integrations.server import MediaServerClient, ServerError, ServerItem
from orion.models import MatchDecision
from orion.routes.server import saved_hints


def expected_signature_fingerprint(signature):
    return hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@pytest.fixture
def hint_runtime(library, tmp_path, context):
    root = tmp_path / 'incoming'
    root.mkdir()
    media = root / 'original.mkv'
    media.write_bytes(b'original media')
    source_id = library.add_source(root, kind='movies')['id']
    Discovery(library).scan([source_id], False, context)
    item = library.query().items[0]
    library.decide(item.id, MatchDecision(item_id=item.id, provider='tmdb', provider_id='42',
                                        metadata={'title': 'Arrival', 'year': '2016'}))
    runtime = SimpleNamespace(store=library.store, library=library,
                              config=Config(tmp_path / 'preferences'), providers=None)
    runtime.server = ServerIntegration(runtime)
    runtime.server.save(ServerSettings(enabled=True, url='http://127.0.0.1:8096', user_id='first'))
    runtime.config.set_api_key('media_server', 'fixture-key', session_only=True)
    return runtime, item.id, media, source_id


def change_observed_state(runtime, item_id, media, source_id, context, change):
    if change == 'signature':
        media.write_bytes(b'a replacement arrival with different content')
        Discovery(runtime.library).scan([source_id], False, context)
    elif change == 'decision':
        runtime.library.decide(item_id, MatchDecision(item_id=item_id, metadata={'title': 'New choice'}))
    elif change == 'clear':
        runtime.library.clear_decision(item_id)
    else:
        runtime.server.save(runtime.server.configuration().model_copy(update={'user_id': 'second'}))
    runtime.library.annotate(item_id, review_note='A concurrent annotation')


@pytest.mark.parametrize('change', ['signature', 'decision', 'clear', 'configuration'])
@pytest.mark.parametrize('request_fails', [False, True])
def test_late_server_hints_never_annotate_changed_item(
    hint_runtime, context, monkeypatch, change, request_fails
):
    runtime, item_id, media, source_id = hint_runtime
    observed = runtime.library.get(item_id)
    payload = {'item_id': item_id, 'server_revision': runtime.server.revision()}

    def delayed_search(client, query, request_context):
        assert query.search == 'Arrival'
        assert query.include_types == 'Movie'
        change_observed_state(runtime, item_id, media, source_id, context, change)
        if request_fails:
            raise ServerError('server_unavailable')
        return [ServerItem(id='old-result', name='Arrival', type='Movie', provider_ids={'tmdb': '42'})]

    monkeypatch.setattr(MediaServerClient, 'items', delayed_search)
    expected_code = 'server_unavailable' if request_fails else (
        'server_configuration_changed' if change == 'configuration' else 'item_changed')
    with pytest.raises(ServerError) as error:
        runtime.server.run('server_hints', payload, context)
    assert error.value.code == expected_code
    latest = runtime.library.get(item_id)
    assert latest.metadata['review_note'] == 'A concurrent annotation'
    assert not any(key.startswith('server_hint') for key in latest.metadata)
    if change == 'signature':
        assert latest.signature != observed.signature and latest.decision is None
    elif change == 'decision':
        assert latest.decision.metadata == {'title': 'New choice'}
    elif change == 'clear':
        assert latest.decision is None


def test_current_hints_save_provenance_and_merge_concurrent_annotations(hint_runtime, context, monkeypatch):
    runtime, item_id, _, _ = hint_runtime
    observed = runtime.library.get(item_id)

    def search(client, query, request_context):
        runtime.library.annotate(item_id, review_note='Keep this annotation')
        return [ServerItem(id='match', name='Arrival', type='Movie', provider_ids={'tmdb': '42'})]

    monkeypatch.setattr(MediaServerClient, 'items', search)
    result = runtime.server.run('server_hints', {'item_id': item_id, 'server_revision': runtime.server.revision()}, context)
    latest = runtime.library.get(item_id)
    assert latest.metadata['review_note'] == 'Keep this annotation'
    assert latest.metadata['server_hint_signature'] == expected_signature_fingerprint(observed.signature)
    assert latest.metadata['server_hint_decision'] == observed.decision.model_dump()
    assert latest.decision == observed.decision and latest.signature == observed.signature
    assert result['complete'] is True
    cached = saved_hints(item_id, runtime)
    assert cached['state'] == 'ready' and cached['items'] == result['items']
    assert 'Confirmed provider identifier agrees' in cached['items'][0]['evidence']


@pytest.mark.parametrize('change', ['signature', 'decision', 'clear', 'configuration'])
def test_cached_hints_reopened_after_observed_state_change_are_hidden(hint_runtime, context, monkeypatch, change):
    runtime, item_id, media, source_id = hint_runtime
    monkeypatch.setattr(MediaServerClient, 'items', lambda *args: [ServerItem(id='match', name='Arrival', type='Movie')])
    runtime.server.run('server_hints', {'item_id': item_id, 'server_revision': runtime.server.revision()}, context)
    assert saved_hints(item_id, runtime)['state'] == 'ready'
    prior_metadata = runtime.library.get(item_id).metadata
    change_observed_state(runtime, item_id, media, source_id, context, change)
    if change == 'signature':
        # Even persisted hint annotations carried into a new scan record are stale.
        runtime.library.annotate(item_id, **{key: value for key, value in prior_metadata.items() if key.startswith('server_hint')})
    assert saved_hints(item_id, runtime) == {'items': [], 'state': 'not_checked', 'error': None}


def test_legacy_hints_without_item_provenance_are_hidden(hint_runtime):
    runtime, item_id, _, _ = hint_runtime
    runtime.library.annotate(item_id, server_hint_revision=runtime.server.revision(),
                             server_hint_state='ready', server_hints=[{'id': 'old', 'name': 'Arrival'}])
    assert saved_hints(item_id, runtime) == {'items': [], 'state': 'not_checked', 'error': None}


@pytest.mark.parametrize('confirmed', [False, True])
@pytest.mark.parametrize('request_fails', [False, True])
def test_current_empty_or_failed_hints_retain_item_state(hint_runtime, context, monkeypatch, confirmed, request_fails):
    runtime, item_id, _, _ = hint_runtime
    if not confirmed:
        runtime.library.clear_decision(item_id)
    observed = runtime.library.get(item_id)

    def search(*args):
        runtime.library.annotate(item_id, review_note='Keep this annotation')
        if request_fails:
            raise ServerError('server_unavailable')
        return []

    monkeypatch.setattr(MediaServerClient, 'items', search)
    payload = {'item_id': item_id, 'server_revision': runtime.server.revision()}
    if request_fails:
        with pytest.raises(ServerError, match='server unavailable'):
            runtime.server.run('server_hints', payload, context)
    else:
        result = runtime.server.run('server_hints', payload, context)
        assert result == {'item_id': item_id, 'items': [], 'complete': True}
    latest = runtime.library.get(item_id)
    assert latest.status == observed.status and latest.decision == observed.decision
    assert latest.signature == observed.signature and latest.path == observed.path
    assert latest.metadata['review_note'] == 'Keep this annotation'
    assert latest.metadata['server_hint_signature'] == expected_signature_fingerprint(observed.signature)
    assert latest.metadata['server_hint_decision'] == (observed.decision.model_dump() if confirmed else None)
    assert saved_hints(item_id, runtime) == {'items': [], 'state': 'unavailable' if request_fails else 'ready',
                                           'error': 'server_unavailable' if request_fails else None}


@pytest.mark.parametrize('filename', [
    'Secret Movie.mkv', 'token.mkv', 'password.mkv', 'credential.mkv', 'api_key.mkv',
])
@pytest.mark.parametrize('request_fails', [False, True], ids=['success', 'error'])
def test_directory_hint_provenance_survives_secret_like_filenames(
    hint_runtime, tmp_path, context, monkeypatch, filename, request_fails
):
    runtime, _, _, _ = hint_runtime
    root = tmp_path / 'directory-source'
    folder = root / 'Arrival'
    folder.mkdir(parents=True)
    (folder / filename).write_bytes(b'original directory media')
    source_id = runtime.library.add_source(root, kind='movies')['id']
    Discovery(runtime.library).scan([source_id], False, context)
    item = runtime.library.at_path(source_id, str(folder))
    runtime.library.decide(item.id, MatchDecision(item_id=item.id, provider='tmdb', provider_id='42',
                                                metadata={'title': 'Arrival'}))
    observed = runtime.library.get(item.id)
    assert observed.signature['type'] == 'directory'
    assert filename in observed.signature['children']

    def search(*args):
        if request_fails:
            raise ServerError('server_unavailable')
        return [ServerItem(id='match', name='Arrival', type='Movie')]

    monkeypatch.setattr(MediaServerClient, 'items', search)
    payload = {'item_id': item.id, 'server_revision': runtime.server.revision()}
    if request_fails:
        with pytest.raises(ServerError, match='server unavailable'):
            runtime.server.run('server_hints', payload, context)
    else:
        runtime.server.run('server_hints', payload, context)
    expected_state = 'unavailable' if request_fails else 'ready'
    assert saved_hints(item.id, runtime)['state'] == expected_state
    latest = runtime.library.get(item.id)
    assert latest.signature == observed.signature
    assert latest.metadata['server_hint_signature'] == expected_signature_fingerprint(observed.signature)
    assert latest.metadata['server_hint_decision'] == observed.decision.model_dump()
    # JSON member order is not an item change and must not invalidate provenance.
    reordered = {key: observed.signature[key] for key in reversed(observed.signature)}
    with runtime.store.transaction() as conn:
        conn.execute('UPDATE orion_items SET signature=? WHERE id=?', (json.dumps(reordered), item.id))
    assert saved_hints(item.id, runtime)['state'] == expected_state
