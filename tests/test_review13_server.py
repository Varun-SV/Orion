"""Server failure health publication must serialize with job cancellation."""
import threading
import time
from types import SimpleNamespace

from orion.config import Config
from orion.integrations.manager import ServerIntegration, ServerSettings
from orion.jobs import JobManager
from orion.providers import ProviderError


def _wait_terminal(manager, job_id):
    deadline = time.monotonic() + 5
    while manager.get(job_id).state not in ('completed', 'failed', 'cancelled') and time.monotonic() < deadline:
        time.sleep(.01)
    return manager.get(job_id)


def _server_job(library, tmp_path, monkeypatch, fail_inside_publication):
    config = Config(tmp_path / 'server-prefs')
    runtime = SimpleNamespace(store=library.store, config=config, providers=None, library=library)
    server = ServerIntegration(runtime)
    server.save(ServerSettings(enabled=True, url='http://127.0.0.1:8096', user_id='user'))
    config.set_api_key('media_server', 'key', session_only=True)

    entered = threading.Event()
    release = threading.Event()
    original = config.set_pref

    def paused_pref(key, value):
        if key == 'server_health' and fail_inside_publication:
            entered.set()
            assert release.wait(5)
        return original(key, value)

    monkeypatch.setattr(config, 'set_pref', paused_pref)
    monkeypatch.setattr(server, 'client', lambda payload: SimpleNamespace(
        test_connection=lambda ctx: (_ for _ in ()).throw(ProviderError('server_unavailable', 'server')),
        users=lambda ctx: []))
    manager = JobManager(library.store, {'server_test': lambda payload, ctx: server.run('server_test', payload, ctx)})
    payload = {'server_revision': server.revision()}
    return config, manager, payload, entered, release, server


def test_cancel_waits_for_failed_server_health_publication(library, tmp_path, monkeypatch):
    config, manager, payload, entered, release, server = _server_job(library, tmp_path, monkeypatch, True)
    try:
        job = manager.submit('server_test', payload)
        assert entered.wait(3)
        finished = threading.Event()
        stopper = threading.Thread(target=lambda: (manager.cancel(job.id), finished.set()), daemon=True)
        stopper.start()
        assert not finished.wait(.1), 'Cancellation must wait while failed health publication commits'
        release.set()
        assert finished.wait(4)
        assert _wait_terminal(manager, job.id).state == 'failed'
        assert config.get_pref('server_health')['health'] == 'unavailable'
    finally:
        release.set()
        manager.shutdown()


def test_cancel_before_failed_server_publication_skips_health_write(library, tmp_path, monkeypatch):
    config, manager, payload, entered, release, server = _server_job(library, tmp_path, monkeypatch, False)
    request_started = threading.Event()
    request_release = threading.Event()
    original_client = server.client

    def delayed_client(payload):
        client = original_client(payload)
        def fail_after_cancel(ctx):
            request_started.set()
            assert request_release.wait(5)
            raise ProviderError('server_unavailable', 'server')
        client.test_connection = fail_after_cancel
        return client

    monkeypatch.setattr(server, 'client', delayed_client)
    try:
        job = manager.submit('server_test', payload)
        assert request_started.wait(3)
        manager.cancel(job.id)
        request_release.set()
        assert _wait_terminal(manager, job.id).state == 'cancelled'
        assert config.get_pref('server_health')['health'] == 'not_checked'
    finally:
        request_release.set()
        manager.shutdown()
