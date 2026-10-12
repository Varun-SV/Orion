import threading
from types import SimpleNamespace

import pytest

from orion.config import Config
from orion.gaps import ProviderMapping
from orion.integrations.manager import ServerIntegration, ServerSettings
from orion.integrations.server import MediaServerClient, ServerError
from orion.jobs import JobManager
from orion.routes.server import saved_mapping
from test_jobs import wait_terminal


@pytest.fixture
def mapping_runtime(library, tmp_path, monkeypatch):
    runtime = SimpleNamespace(store=library.store, config=Config(tmp_path / 'preferences'), providers=None)
    runtime.server = ServerIntegration(runtime)
    runtime.server.save(ServerSettings(enabled=True, url='http://127.0.0.1:8096', user_id='first'))
    runtime.config.set_api_key('media_server', 'fixture-key', session_only=True)
    monkeypatch.setattr(runtime.server.catalogue, 'episodes', lambda *args: {
        'episodes': [], 'cached': True, 'updated_at': '2026-10-09'})
    runtime.jobs = JobManager(runtime.store, {
        'episode_gaps': lambda payload, context: runtime.server.run('episode_gaps', payload, context)})
    yield runtime
    runtime.jobs.shutdown()


def submit_mapping(runtime, provider_id='42'):
    return runtime.server.submit('episode_gaps', {
        'series_id': 'reused-series',
        'mapping': ProviderMapping(provider_id=provider_id, confirmed=True).model_dump()})


@pytest.mark.parametrize('change', [
    {'url': 'http://127.0.0.1:8097'}, {'server_type': 'emby'}, {'user_id': 'second'},
], ids=['url', 'type', 'user'])
@pytest.mark.parametrize('request_fails', [False, True], ids=['success', 'error'])
def test_blocked_old_gap_job_cannot_overwrite_new_server_mapping_or_health(
    mapping_runtime, monkeypatch, change, request_fails
):
    runtime = mapping_runtime
    original = runtime.server.configuration()
    submitted_revision = runtime.server.revision()
    started, release = threading.Event(), threading.Event()
    observed_clients = []

    def episodes(client, series_id, context):
        observed_clients.append((client.base, client.server_type, client.user_id))
        assert series_id == 'reused-series'
        if len(observed_clients) == 1:
            started.set()
            assert release.wait(5)
            if request_fails:
                raise ServerError('server_unavailable')
        return []

    monkeypatch.setattr(MediaServerClient, 'episodes', episodes)
    try:
        old_job = submit_mapping(runtime)
        assert started.wait(3)
        assert runtime.jobs.get(old_job.id).state == 'running'
        runtime.server.save(original.model_copy(update=change))
        assert runtime.server.revision() != submitted_revision
        assert saved_mapping('reused-series', runtime) is None
        current_job = submit_mapping(runtime, '99')
        assert wait_terminal(runtime.jobs, current_job.id).result['state'] == 'ready'
        current_mapping = saved_mapping('reused-series', runtime)
        assert current_mapping == ProviderMapping(provider_id='99', confirmed=True)
        health = {'health': 'connected', 'detail': 'New server is healthy'}
        runtime.config.set_pref('server_health', health)
        release.set()
        stopped = wait_terminal(runtime.jobs, old_job.id)
        assert saved_mapping('reused-series', runtime) == current_mapping
        assert stopped.state == 'failed' and stopped.error == 'server_configuration_changed'
        assert runtime.config.get_pref('server_health') == health
        assert observed_clients[0] == (original.url, original.server_type, original.user_id)
        current = runtime.server.configuration()
        assert observed_clients[1] == (current.url, current.server_type, current.user_id)
        with runtime.store.transaction() as conn:
            assert conn.execute('SELECT value FROM orion_settings WHERE key=?', (
                'server_mapping_' + submitted_revision + '_reused-series',)).fetchone() is None
    finally:
        release.set()


@pytest.mark.parametrize('request_fails', [False, True], ids=['success', 'error'])
def test_current_gap_job_persists_only_ready_mapping(mapping_runtime, monkeypatch, request_fails):
    runtime = mapping_runtime

    def episodes(*args):
        if request_fails:
            raise ServerError('server_unavailable')
        return []

    monkeypatch.setattr(MediaServerClient, 'episodes', episodes)
    job = submit_mapping(runtime)
    stopped = wait_terminal(runtime.jobs, job.id)
    assert stopped.state == 'completed'
    assert stopped.result['state'] == ('unavailable' if request_fails else 'ready')
    expected = None if request_fails else ProviderMapping(provider_id='42', confirmed=True)
    assert saved_mapping('reused-series', runtime) == expected
