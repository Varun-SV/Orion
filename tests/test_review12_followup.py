"""Orion PR #3 review round: shared outputs, cancellation, and scale regressions."""
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
import pytest

from orion.config import Config
from orion.discovery import signature
from orion.executor import Executor
from orion.integrations.manager import ServerIntegration,ServerSettings
from orion.integrations.server import MediaServerClient,ServerItem,ServerQuery
from orion.jobs import JobManager
from orion.library import Library
from orion.models import MediaItem,MatchDecision
from orion.naming import Naming,NamingProfile,valid_relative
from orion.planner import Planner,PlanOptions
from orion.services import Services
from orion.store import item_id
from tests_support import make_plan


@pytest.mark.parametrize('when',['before_preflight','after_preflight'])
def test_directory_move_keeps_unpreviewed_empty_folder(library,tmp_path,context,when):
    planner,original,source,target=make_plan(library,tmp_path,context,directory=True)
    root=source.parent
    nested=root/'existing-empty'
    if when=='before_preflight':
        nested.mkdir()
    # Even a freshly planned directory contains no entries for empty folders.
    with library.store.transaction() as conn:
        dest=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan=planner.create([original.operations[0].item_id],PlanOptions(destination_id=dest))
    if when=='after_preflight':
        nested.mkdir()
    executor=Executor(library,planner)
    result=executor.execute(plan.id,plan.revision,context)
    assert nested.is_dir(), 'An unpreviewed empty directory must not be deleted'
    assert target.is_file(), 'Approved media may move, but the residual must be reported'
    item=library.get(original.operations[0].item_id)
    assert item.status=='error'
    assert item.metadata.get('recovery_paths')
    assert result.state in ('partial','completed')


def test_undo_retains_sidecars_owned_by_different_album_track(library,tmp_path,context):
    from orion.models import MatchDecision
    source=tmp_path/'incoming';source.mkdir()
    dest=tmp_path/'organised';dest.mkdir()
    sid=library.add_source(source,kind='music')['id']
    ids=[]
    for number in (1,2):
        file=source/f'{number}.flac';file.write_bytes(('song'+str(number)).encode())
        iid='song-'+str(number)
        library.upsert(MediaItem(id=iid,source_id=sid,path=str(file),kind='music',signature=signature(file),
            metadata={'title':'Track '+str(number)},status='approved',
            decision=MatchDecision(item_id=iid,metadata={'title':'Track '+str(number),
                       'artist':'Same Artist','album':'Same Album','track_number':str(number)})))
        ids.append(iid)
    did=item_id('destination',dest)
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)',(did,str(dest),'Destination'))
    planner=Planner(library)
    plan=planner.create(ids,PlanOptions(destination_id=did,profile=NamingProfile(nfo_enabled=True)))
    assert not plan.issues
    shared=[op for op in plan.operations if op.kind=='create_nfo']
    assert shared and all(op.item_id==ids[0] for op in shared)
    executor=Executor(library,planner)
    result=executor.execute(plan.id,plan.revision,context)
    assert result.state=='completed'
    second_move=next(op for op in executor.operations(plan.id) if op.kind=='move' and op.item_id==ids[1])
    undo=executor.undo_plan(result.batch_id,[second_move.id])
    assert not any(op.kind=='remove_created' and op.source in {s.destination for s in shared} for op in undo.operations)
    assert sum(w.code=='sidecar_retained_for_excluded_media' for w in undo.warnings)>=len(shared)
    assert all(Path(op.destination).exists() for op in shared)


def test_unavailable_confirmation_preserves_source_status(library,tmp_path):
    src=tmp_path/'sample.mkv';src.write_bytes(b'video')
    item=MediaItem(id='fixture',source_id='source',path=str(src),kind='movies',
                   signature=signature(src),status='unavailable')
    library.upsert(item)
    new=library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Arrival'}),
                       signature_token=item.signature_token)
    assert new.status=='unavailable'
    assert new.decision is not None
    cleared=library.clear_decision(item.id)
    assert cleared.status=='unavailable'


def test_portable_naming_shortens_unicode_without_name_collision():
    from orion.naming import clean
    first='📺'*150+'A'
    second='📺'*150+'B'
    assert clean(first)==clean(first)
    assert clean(first)!=clean(second)
    assert len(clean(first).encode('utf-8'))<=160
    assert len(clean(second).encode('utf-8'))<=160
    item=MediaItem(id='fixture',source_id='src',path='incoming.mkv',kind='movies',
        decision=MatchDecision(item_id='fixture',metadata={'title':first}))
    path=Naming.render(item,NamingProfile()).path
    assert all(len(part.encode('utf-8'))<=240 for part in Path(path).parts)
    with pytest.raises(ValueError,match='240-byte'):
        valid_relative('a'*241+'/film.mkv')
    with pytest.raises(ValueError,match='240-byte'):
        Naming.render(item,NamingProfile(movie_template='x'*241+'/{title}{ext}'))


def test_server_hint_search_requests_small_transport_limit(library,tmp_path,monkeypatch,context):
    cfg=Config(tmp_path/'server-prefs')
    runtime=SimpleNamespace(store=library.store,config=cfg,providers=None,library=library)
    server=ServerIntegration(runtime)
    server.save(ServerSettings(enabled=True,url='http://127.0.0.1:8096',user_id='user'))
    cfg.set_api_key('media_server','key',session_only=True)
    source=tmp_path/'incoming';source.mkdir()
    file=source/'movie.mkv';file.write_bytes(b'film')
    item=MediaItem(id='movie',source_id='source',path=str(file),kind='movies',
                   signature=signature(file),metadata={'title':'Common'})
    library.upsert(item)
    seen=[]
    def fake_items(self,query,ctx):
        seen.append(query.max_items)
        return [ServerItem(id=str(n),name='Common',type='Movie') for n in range(100)]
    monkeypatch.setattr(MediaServerClient,'items',fake_items)
    result=server.run('server_hints',{'server_revision':server.revision(),'item_id':item.id},context)
    assert seen==[30]
    assert len(result['items'])==30
    assert len(server.saved_hints(item.id)['items'])==30


def test_real_server_client_stops_at_hint_limit(monkeypatch,context):
    client=MediaServerClient('http://127.0.0.1:8096','key',user_id='user')
    requested=[]
    def page(method,path,ctx,params=None):
        requested.append(params.copy())
        start=params['StartIndex']
        return {'TotalRecordCount':100000,'Items':[{'Id':str(i),'Name':'Common','Type':'Movie'} for i in range(start,start+params['Limit'])]}
    monkeypatch.setattr(client,'_call',page)
    hints=client.items(ServerQuery(search='Common',max_items=30),context)
    assert len(hints)==30 and len(requested)==1
    assert requested[0]['Limit']==30


@pytest.mark.parametrize('kind,output',[
    ('provider_test',{'provider':'tmdb','health':'connected','detail':'ok'}),
    ('server_test',{'server':{'id':'one'},'users':[]}),
    ('server_refresh',{'accepted':True,'detail':'Server accepted'}),
])
def test_cancel_after_committed_result_is_not_misreported(library,kind,output):
    def accepted(payload,ctx):
        ctx.event.set()
        return output
    manager=JobManager(library.store,{kind:accepted})
    try:
        job=manager.submit(kind,{'provider':'tmdb'} if kind=='provider_test' else {})
        deadline=time.monotonic()+5
        while manager.get(job.id).state not in ('completed','failed','cancelled') and time.monotonic()<deadline:
            time.sleep(.01)
        assert manager.get(job.id).state=='completed'
    finally:manager.shutdown()


def test_cancel_waits_for_provider_health_publication(library,tmp_path,monkeypatch):
    cfg=Config(tmp_path/'provider-prefs')
    services=Services(cfg,library.store,library,None,None,None,None)
    entered=threading.Event()
    release=threading.Event()
    original=cfg.set_pref
    def slow_pref(key,value):
        if key=='provider_health_tmdb':
            entered.set()
            assert release.wait(5)
        return original(key,value)
    monkeypatch.setattr(cfg,'set_pref',slow_pref)
    monkeypatch.setattr(services,'_test_provider',lambda payload,ctx:{'health':'connected','detail':'ok'})
    manager=JobManager(library.store,{'provider_test':services.test_provider})
    try:
        job=manager.submit('provider_test',{'provider':'tmdb'})
        assert entered.wait(3)
        finished=threading.Event()
        stopper=threading.Thread(target=lambda:(manager.cancel(job.id),finished.set()),daemon=True)
        stopper.start()
        assert not finished.wait(.1), 'Cancellation must wait while a health value commits'
        release.set()
        assert finished.wait(4)
        deadline=time.monotonic()+5
        while manager.get(job.id).state not in ('completed','failed','cancelled') and time.monotonic()<deadline:
            time.sleep(.01)
        assert manager.get(job.id).state=='completed'
        assert cfg.get_pref('provider_health_tmdb')['health']=='connected'
    finally:
        release.set()
        manager.shutdown()


def test_selection_endpoint_looks_up_ids_beyond_first_page(tmp_path):
    from fastapi.testclient import TestClient
    from orion.app import create_app
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1:4321') as client:
        client.headers['X-Orion-CSRF']=client.get('/api/v1/session').json()['csrf_token']
        runtime=client.app.state.services
        with runtime.store.transaction() as conn:
            for index in range(505):
                conn.execute('INSERT INTO orion_items VALUES(?,?,?,?,?,?,?,?,?)',(
                    'item-'+str(index),'src','/media/'+str(index).zfill(4)+'.mkv',
                    'movies','approved','{}',json.dumps({'title':'Video'}),None,'now'))
        selected=['item-504','item-1']
        response=client.post('/api/v1/items/selection',json={'item_ids':selected})
        assert response.status_code==200, response.text
        assert [item['id'] for item in response.json()]==selected
        assert client.post('/api/v1/items/selection',json={'item_ids':['not-here']}).status_code==404
        assert client.post('/api/v1/items/selection',json={'item_ids':['i']*501}).status_code==422
