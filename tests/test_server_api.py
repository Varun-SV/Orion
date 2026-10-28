from test_api import client,wait_job
from test_media_server import server_fixture
from tests_support import make_plan

def configure(client,url,auto_refresh=False):
    response=client.put('/api/v1/server',json={'enabled':True,'url':url,'server_type':'jellyfin','user_id':'chosen-user','auto_refresh':auto_refresh})
    assert response.status_code==200
    assert client.post('/api/v1/server/credentials',json={'key':'private-server-key','session_only':True}).status_code==200

def test_server_jobs_select_user_and_store_no_credentials(client,server_fixture,tmp_path):
    url,state=server_fixture;configure(client,url)
    settings=client.get('/api/v1/server').json()
    assert settings['configured'] and settings['health']=='not_checked'
    assert 'private-server-key' not in str(settings)
    test=client.post('/api/v1/server/test').json();result=wait_job(client,test['id'])
    assert result['state']=='completed' and len(result['result']['users'])==2
    assert client.get('/api/v1/server').json()['health']=='connected'
    discovered=client.post('/api/v1/server/discover',json={'include_types':'Series'}).json()
    assert len(wait_job(client,discovered['id'])['result']['items'])==125
    state['status']=401
    failed=client.post('/api/v1/server/test').json()
    assert wait_job(client,failed['id'])['state']=='failed'
    assert client.get('/api/v1/server').json()['health']=='unavailable'
    with client.app.state.services.store.transaction() as conn:
        assert 'private-server-key' not in str([tuple(r) for r in conn.execute('SELECT payload,result,error FROM orion_jobs')])
    assert 'private-server-key' not in (tmp_path/'prefs.json').read_text()

def test_refresh_failure_is_independently_retryable_and_preserves_local_success(client,server_fixture,tmp_path,context):
    url,state=server_fixture;configure(client,url,auto_refresh=True)
    runtime=client.app.state.services
    (tmp_path/'files').mkdir()
    planner,plan,source,target=make_plan(runtime.library,tmp_path/'files',context)
    state['status']=500
    job=client.post('/api/v1/plans/'+plan.id+'/execute',json={'revision':1}).json()
    local=wait_job(client,job['id'])
    assert local['state']=='completed' and target.exists() and not source.exists()
    refresh=wait_job(client,local['result']['refresh_job_id'])
    assert refresh['state']=='failed' and refresh['error']=='server_unavailable'
    state['status']=200
    assert client.post('/api/v1/jobs/'+refresh['id']+'/retry').status_code==200
    assert wait_job(client,refresh['id'])['state']=='completed'
    assert target.exists() and not source.exists()

def test_gap_without_mapping_does_not_request_server_or_report_missing(client,server_fixture):
    url,state=server_fixture;configure(client,url)
    job=client.post('/api/v1/server/gaps',json={'series_id':'series','mapping':{'provider_id':'42','confirmed':False}}).json()
    result=wait_job(client,job['id'])
    assert result['result']['state']=='mapping_required' and result['result']['missing']==[]
    assert state['requests']==[]

def test_late_metadata_annotation_preserves_a_concurrent_confirmed_match(library,tmp_path,context,monkeypatch):
    from tests_support import make_plan
    from orion.models import MatchDecision
    planner,plan,source,target=make_plan(library,tmp_path,context)
    item=library.query().items[0]
    import orion.library as module
    original=module.safe_metadata
    armed=[True]
    def concurrent_sanitize(metadata):
        if armed[0] and 'server_hints' in metadata:
            armed[0]=False
            library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Updated decision'}))
        return original(metadata)
    monkeypatch.setattr(module,'safe_metadata',concurrent_sanitize)
    library.annotate(item.id,server_hints=[{'name':'Example'}])
    assert library.get(item.id).decision.metadata['title']=='Updated decision'

def test_server_hints_cache_cannot_be_reused_after_switching_server_context(client,server_fixture,tmp_path,context):
    url,state=server_fixture;configure(client,url)
    runtime=client.app.state.services
    planner,plan,source,target=make_plan(runtime.library,tmp_path,context)
    item=runtime.library.query().items[0]
    hints=client.post('/api/v1/items/'+item.id+'/server-hints').json()
    assert wait_job(client,hints['id'])['state']=='completed'
    assert client.get('/api/v1/items/'+item.id+'/server-hints').json()['state']=='ready'
    assert client.put('/api/v1/server',json={'enabled':True,'url':url,'server_type':'jellyfin','user_id':'other'}).status_code==200
    cached=client.get('/api/v1/items/'+item.id+'/server-hints').json()
    assert cached['state']=='not_checked' and cached['items']==[]


def test_disabled_server_session_key_can_be_cleared_without_keychain(client,monkeypatch):
    import keyring
    runtime=client.app.state.services
    runtime.config.set_api_key('media_server','session-fixture',session_only=True)
    assert not client.get('/api/v1/server').json()['configured']
    assert runtime.config.get_api_key('media_server')=='session-fixture'
    def unavailable(*args):
        raise keyring.errors.NoKeyringError('No OS credential vault')
    monkeypatch.setattr(keyring,'delete_password',unavailable)
    for _ in range(2):
        response=client.delete('/api/v1/server/credentials')
        assert response.status_code==200
        assert response.json()=={'configured':False}
        assert runtime.config.get_api_key('media_server')==''
    assert client.get('/api/v1/server').json()['storage']=='session'


def test_disabled_server_keychain_key_is_removed_from_selected_storage(client):
    import keyring
    runtime=client.app.state.services
    runtime.config.set_api_key('media_server','keychain-fixture')
    assert not client.get('/api/v1/server').json()['configured']
    assert keyring.get_password('Orion','media_server')=='keychain-fixture'
    response=client.delete('/api/v1/server/credentials')
    assert response.status_code==200
    assert runtime.config.get_api_key('media_server')==''
    assert keyring.get_password('Orion','media_server') is None
    assert client.get('/api/v1/server').json()['storage']=='keychain'
