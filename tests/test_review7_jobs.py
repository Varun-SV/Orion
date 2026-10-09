"""Regressions for excluded specials and cancelled lookup publication."""
import csv
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from orion.config import Config
from orion.discovery import Discovery
from orion.gaps import EpisodeGaps, ProviderMapping, TmdbCatalogue
from orion.integrations.server import MediaServerClient
from orion.jobs import JobManager
from orion.models import MatchDecision
from orion.providers import Providers
from orion.reports import Reports
from orion.services import Services
from test_jobs import wait_terminal


@pytest.fixture
def mixed_episode_server():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = {'TotalRecordCount': 2, 'Items': [
                {'Id': 'special', 'Name': 'Special double episode', 'Type': 'Episode',
                 'ParentIndexNumber': 0, 'IndexNumber': 1, 'IndexNumberEnd': 2},
                {'Id': 'regular', 'Name': 'Regular double episode', 'Type': 'Episode',
                 'ParentIndexNumber': 1, 'IndexNumber': 1, 'IndexNumberEnd': 2},
            ]}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


@pytest.mark.parametrize('server_type', ['jellyfin', 'emby'])
@pytest.mark.parametrize('include_specials,expected_present,expected_missing', [
    (False, [[1, 1], [1, 2]], [[1, 3]]),
    (True, [[0, 1], [0, 2], [1, 1], [1, 2]], [[0, 3], [1, 3]]),
])
def test_specials_policy_applies_to_persisted_counts_and_exports(
    library, tmp_path, context, mixed_episode_server,
    server_type, include_specials, expected_present, expected_missing,
):
    config = Config(tmp_path / 'prefs')
    config.set_api_key('tmdb', 'fixture-key', session_only=True)

    def catalogue_request(provider, method, url, ctx, **kwargs):
        if '/season/' not in url:
            return {'seasons': [{'season_number': 0, 'episode_count': 3},
                                {'season_number': 1, 'episode_count': 3}]}
        return {'episodes': [{'episode_number': number, 'air_date': '2020-01-01',
                              'name': f'Episode {number}', 'overview': 'Fixture plot'}
                             for number in (1, 2, 3)]}

    catalogue = TmdbCatalogue(library.store, Providers(config, request=catalogue_request))
    catalogue.episodes('42', True, context)
    cached_specials = catalogue.get_cached('tv/42/season/0')
    assert cached_specials is not None and len(cached_specials[0]['episodes']) == 3

    def offline(*args, **kwargs):
        pytest.fail('Fresh cached catalogue must not perform provider I/O')

    catalogue.providers.request = offline
    server = MediaServerClient(mixed_episode_server, 'fixture-key', server_type, 'fixture-user')
    gaps = EpisodeGaps(server, catalogue)
    manager = JobManager(library.store, {'episode_gaps': lambda p, c: gaps.compare(
        'series', ProviderMapping(provider_id='42', confirmed=True), include_specials, c)})
    try:
        job = manager.submit('episode_gaps', {})
        completed = wait_terminal(manager, job.id)
        assert completed.state == 'completed'
        result = completed.result
        assert result['state'] == 'ready'
        assert result['present'] == expected_present
        assert result['missing'] == expected_missing
        assert result['catalogue_cached'] is True
        assert len(result['present']) == (4 if include_specials else 2)
        assert len(result['episodes']) == (6 if include_specials else 3)
        assert result['unaired'] == [] and result['unknown_air_date'] == []
        if not include_specials:
            assert all(episode['season'] == 1 for episode in result['episodes'])
        exported_json = json.loads(Reports(library.store).export(job.id, 'json'))
        assert exported_json['job']['result']['present'] == expected_present
        exported_csv = next(csv.DictReader(io.StringIO(
            Reports(library.store).export(job.id, 'csv').decode())))
        assert json.loads(exported_csv['result'])['present'] == expected_present
        assert catalogue.get_cached('tv/42/season/0') == cached_specials
    finally:
        manager.shutdown()
        server._session.close()


@pytest.mark.parametrize('provider_result', ['success', 'error'])
@pytest.mark.parametrize('status', ['pending', 'approved', 'organised'])
@pytest.mark.parametrize('cancel', [True, False])
def test_provider_finishing_after_cancellation_preserves_lookup_state(
    library, tmp_path, context, provider_result, status, cancel,
):
    root = tmp_path / 'incoming'
    root.mkdir()
    (root / 'Arrival (2016).mkv').write_bytes(b'fixture-media')
    sid = library.add_source(root, kind='movies')['id']
    Discovery(library).scan([sid], False, context)
    item = library.query().items[0]
    previous_candidates = [{'provider': 'tmdb', 'provider_id': 'old', 'title': 'Existing'}]
    library.annotate(item.id, candidates=previous_candidates,
                     lookup_state='ready', lookup_error=None)
    if status != 'pending':
        library.decide(item.id, MatchDecision(item_id=item.id, metadata={'title': 'Confirmed'}))
        library.status(item.id, status)
    before = library.get(item.id)
    config = Config(tmp_path / 'prefs')
    config.set_api_key('tmdb', 'fixture-key', session_only=True)
    started, release = threading.Event(), threading.Event()

    def final_provider_request(provider, method, url, ctx, **kwargs):
        started.set()
        assert release.wait(5)
        if provider_result == 'error':
            raise requests.Timeout('fixture provider timeout')
        return {'results': [{'id': 42, 'title': 'Fresh result', 'release_date': '2016-01-01',
                             'overview': 'Fixture plot', 'poster_path': None}]}

    providers = Providers(config, request=final_provider_request)
    services = Services(config, library.store, library, None, providers, None, None)
    manager = JobManager(library.store, {'lookup': services.lookup})
    try:
        job = manager.submit('lookup', {'item_id': item.id, 'provider': 'tmdb'})
        assert started.wait(5)
        if cancel:
            assert manager.cancel(job.id).state == 'cancelling'
        release.set()
        terminal = wait_terminal(manager, job.id)
        after = library.get(item.id)
        if cancel:
            assert after == before
            assert terminal.state == 'cancelled'
            assert terminal.error is None and terminal.result is None
        elif provider_result == 'success':
            assert terminal.state == 'completed'
            assert after.metadata['candidates'][0]['title'] == 'Fresh result'
            assert after.metadata['lookup_state'] == 'ready'
            assert after.status == status
        else:
            assert terminal.state == 'failed' and terminal.error == 'provider_unavailable'
            assert after.metadata['candidates'] == previous_candidates
            assert after.metadata['lookup_state'] == 'error'
            assert after.status == ('error' if status == 'pending' else status)
        assert after.decision == before.decision
        assert after.signature == before.signature
    finally:
        release.set()
        manager.shutdown()
