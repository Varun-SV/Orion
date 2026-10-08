from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from orion.app import create_app

@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app,base_url='http://127.0.0.1:4321') as client:
        session = client.get('/api/v1/session').json()
        client.headers['X-Orion-CSRF'] = session['csrf_token']
        yield client

def test_local_session_is_required_for_mutations(tmp_path):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1:4321') as client:
        assert client.post('/api/v1/jobs',json={'kind':'scan','payload':{'source_ids':[]}}).status_code == 403
        response = client.get('/api/v1/session')
        assert response.status_code == 200
        assert 'HttpOnly' in response.headers['set-cookie']
        assert 'SameSite=strict' in response.headers['set-cookie']
        assert client.put('/api/v1/settings',json={'theme':'night'}).status_code == 403

def test_cross_origin_loopback_mutations_are_rejected(client):
    hostile = {'Origin':'https://hostile.example','X-Orion-CSRF':client.headers['X-Orion-CSRF']}
    assert client.post('/api/v1/jobs',json={'kind':'scan','payload':{'source_ids':[]}},headers=hostile).status_code == 403
    assert client.get('/api/v1/session',headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
    assert client.get('/api/v1/health',headers={'Host':'hostile.example'}).status_code == 400

def test_overview_imports_all_media_metrics(legacy):
    with TestClient(create_app(legacy.parent),base_url='http://127.0.0.1:4321') as client:
        counts = client.get('/api/v1/overview').json()['counts']
        assert counts['movies'] == 2
        assert counts['music'] == 1
        assert counts['books'] == 1
        assert sum(counts.values()) == 4

def test_sources_settings_and_credentials_are_real_and_strict(client,tmp_path):
    source = tmp_path/'incoming'
    source.mkdir()
    added = client.post('/api/v1/sources',json={'path':str(source),'kind':'movies'})
    assert added.status_code == 201
    assert client.get('/api/v1/overview').json()['sources'] == 1
    assert client.post('/api/v1/sources',json={'path':str(source),'unknown':True}).status_code == 422
    assert client.put('/api/v1/settings',json={'theme':'night'}).status_code == 200
    assert client.get('/api/v1/settings').json()['theme'] == 'night'
    assert client.put('/api/v1/settings',json={'theme':'wrong'}).status_code == 422
    saved = client.post('/api/v1/providers/tmdb/credentials',json={'key':'private-key','session_only':True})
    assert saved.status_code == 200
    status = client.get('/api/v1/providers')
    assert 'private-key' not in status.text
    assert next(r for r in status.json() if r['id']=='tmdb')['configured'] is True
    assert any(r['id']=='acoustid' for r in status.json())
    assert 'private-key' not in (tmp_path/'prefs.json').read_text()

def test_unknown_resources_do_not_fall_back_to_index(client):
    assert client.get('/api/v1/items/missing').status_code == 404
    assert client.get('/api/v1/not-a-route').status_code == 404

def test_static_spa_fallback_does_not_expose_project_files(tmp_path):
    frontend = tmp_path/'frontend'
    frontend.mkdir()
    (frontend/'index.html').write_text('<html>Orion production shell</html>')
    (tmp_path/'secret.txt').write_text('not public')
    with TestClient(create_app(tmp_path/'data',frontend),base_url='http://127.0.0.1:4321') as client:
        assert 'Orion production shell' in client.get('/review').text
        assert 'not public' not in client.get('/%2e%2e/secret.txt').text
        assert client.get('/assets/missing.js').status_code == 404

def wait_job(client,job_id):
    import time
    deadline = time.monotonic()+8
    while time.monotonic()<deadline:
        result = client.get('/api/v1/jobs/'+job_id).json()
        if result['state'] in ('completed','failed','cancelled','interrupted'):
            return result
        time.sleep(0.02)
    pytest.fail('API job did not finish')

def test_actual_scan_review_plan_move_and_undo_flow(client,tmp_path):
    root = tmp_path/'incoming'
    dest = tmp_path/'organised'
    root.mkdir()
    dest.mkdir()
    media = root/'original.mkv'
    media.write_bytes(b'API media fixture')
    source = client.post('/api/v1/sources',json={'path':str(root),'kind':'movies'}).json()
    destination = client.post('/api/v1/destinations',json={'path':str(dest)}).json()
    scan = client.post('/api/v1/jobs',json={'kind':'scan','payload':{'source_ids':[source['id']]}})
    assert scan.status_code==202
    assert wait_job(client,scan.json()['id'])['state']=='completed'
    item = client.get('/api/v1/items').json()['items'][0]
    review = client.put('/api/v1/items/'+item['id']+'/decision',json={'item_id':item['id'],'metadata':{'title':'Arrival','year':'2016'}})
    assert review.status_code==200
    created = client.post('/api/v1/plans',json={'item_ids':[item['id']],'options':{'destination_id':destination['id']}})
    assert created.status_code==201 and not created.json()['issues']
    plan = created.json()
    # A nested transaction in plan-listing must not deadlock on its own write lock.
    store = client.app.state.services.store
    original_connection = store._connection
    def quick_connection():
        conn = original_connection()
        conn.execute('PRAGMA busy_timeout=50')
        return conn
    store._connection = quick_connection
    assert client.get('/api/v1/plans').json()[0]['id']==plan['id']
    assert media.read_bytes()==b'API media fixture'
    execution = client.post('/api/v1/plans/'+plan['id']+'/execute',json={'revision':1})
    assert execution.status_code==202
    result = wait_job(client,execution.json()['id'])
    assert result['state']=='completed'
    target = Path(plan['operations'][0]['destination'])
    assert target.read_bytes()==b'API media fixture' and not media.exists()
    undo = client.post('/api/v1/batches/'+result['result']['batch_id']+'/undo-plan').json()
    assert not undo['issues']
    reverse = client.post('/api/v1/plans/'+undo['id']+'/execute',json={'revision':1})
    assert reverse.json()['kind']=='undo'
    assert wait_job(client,reverse.json()['id'])['state']=='completed'
    assert media.read_bytes()==b'API media fixture' and not target.exists()
    assert client.get('/api/v1/activity').json()

def test_nested_job_payload_rejects_unknown_fields_without_echoing_secrets(client):
    response = client.post('/api/v1/jobs',json={'kind':'scan','payload':{'source_ids':[],'api_key':'secret-value'}})
    assert response.status_code==422
    assert 'secret-value' not in response.text

def test_archiving_source_updates_active_source_metric(client,tmp_path):
    root = tmp_path/'archive-source'
    root.mkdir()
    source = client.post('/api/v1/sources',json={'path':str(root),'kind':'movies'}).json()
    assert client.delete('/api/v1/sources/'+source['id']).status_code == 200
    assert root.exists()
    assert client.get('/api/v1/overview').json()['sources'] == 0
    assert client.get('/api/v1/sources').json()[0]['archived'] is True

def test_startup_recovery_does_not_block_api_and_can_be_cancelled(tmp_path,monkeypatch):
    import threading,time
    from orion.executor import Executor
    from orion.discovery import Cancelled
    from orion.models import OperationPlan,Operation
    from orion.store import Store
    from orion.library import Library
    from orion.planner import Planner
    store = Store(tmp_path/'organizer.db')
    store.migrate()
    planner = Planner(Library(store))
    planner.save(OperationPlan(id='interrupted-plan',operations=[Operation(id='interrupted-op',plan_id='interrupted-plan',item_id='fixture',source='source',destination='target',expected_signature={},state='intent')]))
    entered = threading.Event()
    exited = threading.Event()
    def slow_recovery(self,plan_id=None,context=None):
        entered.set()
        try:
            until = time.monotonic()+2
            while time.monotonic()<until:
                if context and context.cancelled(): raise Cancelled()
                time.sleep(.01)
            raise AssertionError('Recovery was not cancellable')
        finally:
            exited.set()
    monkeypatch.setattr(Executor,'reconcile',slow_recovery)
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1:4321') as client:
        assert entered.wait(1)
        assert not exited.is_set(), 'API startup waited for recovery hashing'
        assert client.get('/api/v1/health').status_code == 200
        token = client.get('/api/v1/session').json()['csrf_token']
        client.headers['X-Orion-CSRF'] = token
        recovery = next(j for j in client.get('/api/v1/jobs').json() if j['kind']=='recovery')
        client.post('/api/v1/jobs/'+recovery['id']+'/cancel')
        assert wait_job(client,recovery['id'])['state']=='cancelled'
        assert exited.wait(1)
