import json
import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
import requests
from fastapi.testclient import TestClient
from orion.app import create_app
from orion.config import Config
from orion.discovery import Discovery
from orion.executor import Executor
from orion.jobs import JobManager
from orion.models import MediaItem, MatchDecision
from orion.naming import Naming, NamingProfile
from orion.providers import Providers, ProviderError
from orion.services import Services
from orion.store import Store
from tests_support import make_plan
from test_jobs import wait_terminal

@pytest.mark.parametrize('deep',[False,True])
def test_directory_without_media_becomes_unavailable_and_can_return(library,tmp_path,context,deep):
    root=tmp_path/'incoming';folder=root/'Film';folder.mkdir(parents=True)
    media=folder/'film.mkv';media.write_bytes(b'film');(folder/'film.srt').write_bytes(b'subtitle')
    sid=library.add_source(root,kind='movies')['id'];scanner=Discovery(library)
    scanner.scan([sid],False,context);item=library.query().items[0]
    decision=MatchDecision(item_id=item.id,metadata={'title':'Film'});library.decide(item.id,decision)
    media.unlink();scanner.scan([sid],deep,context)
    assert library.get(item.id).status=='unavailable'
    assert library.get(item.id).decision==decision
    scanner.scan([sid],deep,context);assert library.get(item.id).status=='unavailable'
    media.write_bytes(b'new media');scanner.scan([sid],deep,context)
    assert library.get(item.id).status=='pending' and library.get(item.id).decision is None

def test_rescan_does_not_mark_organised_destination_unavailable(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    Executor(library,planner).execute(plan.id,1,context)
    item=library.get(plan.operations[0].item_id)
    Discovery(library).scan([item.source_id],False,context)
    assert library.get(item.id).status=='organised' and library.get(item.id).path==str(target)

@pytest.mark.parametrize('root_first',[True,False])
def test_filesystem_root_sources_cannot_overlap(library,tmp_path,root_first):
    root=Path(tmp_path.anchor)
    first,second=(root,tmp_path) if root_first else (tmp_path,root)
    library.add_source(first)
    with pytest.raises(ValueError,match='overlap'):library.add_source(second)
    assert len(library.sources())==1

@pytest.mark.parametrize('native_junction_check',[True,False])
def test_source_rejects_linked_ancestor(library,tmp_path,monkeypatch,native_junction_check):
    if not native_junction_check:
        monkeypatch.setattr(Path,'is_junction',lambda self:False,raising=False)
    target=tmp_path/'real';(target/'child').mkdir(parents=True);link=tmp_path/'link'
    if os.name=='nt':
        import _winapi
        _winapi.CreateJunction(str(target),str(link))
    else:link.symlink_to(target,target_is_directory=True)
    try:
        assert (link/'child').is_dir() and not (link/'child').is_symlink()
        with pytest.raises(ValueError,match='link'):library.add_source(link/'child')
        assert library.sources()==[]
    finally:link.rmdir() if os.name=='nt' else link.unlink()

@pytest.mark.parametrize('kind,extension',[('music','.wav'),('books','.pdf')])
def test_nonvideo_sources_skip_stray_video_files(library,tmp_path,context,kind,extension):
    root=tmp_path/kind;root.mkdir();(root/('valid'+extension)).write_bytes(b'fixture');(root/'stray.mkv').write_bytes(b'video')
    sid=library.add_source(root,kind=kind)['id'];summary=Discovery(library).scan([sid],False,context)
    assert summary.processed==1
    assert [Path(i.path).name for i in library.query().items]==['valid'+extension]

@pytest.mark.parametrize('error,code',[
    (requests.Timeout('private-key'), 'provider_unavailable'),
    (requests.ConnectionError('private-key'), 'provider_unavailable'),
    (requests.HTTPError('private-key'), 'provider_unavailable'),
])
def test_transport_failed_provider_test_updates_stale_health(tmp_path,context,error,code):
    cfg=Config(tmp_path);cfg.set_pref('provider_health_musicbrainz',{'health':'connected','detail':'old success'})
    def fail(*a,**k):raise error
    providers=Providers(cfg,request=fail)
    runtime=Services(cfg,None,None,None,providers,None,None)
    with pytest.raises(ProviderError) as exc:runtime.test_provider({'provider':'musicbrainz'},context)
    assert exc.value.code==code and 'private-key' not in str(exc.value)
    assert cfg.get_pref('provider_health_musicbrainz')=={'health':'unavailable','detail':code}

@pytest.mark.parametrize('status,code',[(401,'credentials_rejected'),(403,'credentials_rejected'),(503,'provider_unavailable')])
def test_provider_test_http_failures_have_safe_job_error(library,tmp_path,status,code):
    cfg=Config(tmp_path);cfg.set_api_key('tmdb','fixture',session_only=True)
    response=requests.Response();response.status_code=status
    def fail(*a,**k):raise requests.HTTPError('https://api/?api_key=private-key',response=response)
    runtime=Services(cfg,library.store,library,None,Providers(cfg,request=fail),None,None)
    manager=JobManager(library.store,{'provider_test':runtime.test_provider})
    try:
        job=manager.submit('provider_test',{'provider':'tmdb'})
        final=wait_terminal(manager,job.id)
        assert final.state=='failed' and final.error==code
        assert cfg.get_pref('provider_health_tmdb')=={'health':'unavailable','detail':code}
        assert 'private-key' not in final.model_dump_json()
    finally:manager.shutdown()

@pytest.mark.parametrize('migrated',[False,True])
def test_lookup_honors_displayed_category_provider_after_startup(tmp_path,legacy,context,monkeypatch,migrated):
    if migrated:
        import sqlite3
        with sqlite3.connect(legacy) as conn:conn.execute("INSERT INTO categories(name,media_type,api_pref,dest_subpath) VALUES('Japanese shows','anime','anidb','Anime')")
    directory=legacy.parent if migrated else tmp_path/'fresh'
    with TestClient(create_app(directory),base_url='http://127.0.0.1:4321') as client:
        runtime=client.app.state.services
        category=next(c for c in client.get('/api/v1/categories').json() if c['kind']=='anime' and (not migrated or c['name']=='Japanese shows'))
        expected=category['api_pref'];seen=[]
        assert {c['api_pref'] for c in client.get('/api/v1/categories').json() if c['kind']=='anime'}=={expected}
        for provider in ('tmdb','anilist','anidb'):
            monkeypatch.setattr(runtime.providers,'_'+provider,lambda *a,provider=provider:seen.append(provider) or [])
        item=MediaItem(id='anime',source_id='s',path='missing.mkv',kind='anime')
        assert runtime.providers.candidates(item,context)==[] and seen==[expected]
        runtime.config.set_pref('provider_anime','anilist')
        runtime.providers.candidates(item,context);assert seen[-1]=='anilist'
        assert {c['api_pref'] for c in client.get('/api/v1/categories').json() if c['kind']=='anime'}=={'anilist'}
        runtime.providers.candidates(item,context,provider='tmdb');assert seen[-1]=='tmdb'

@pytest.mark.parametrize('filename',['Arrival.txt','Arrival','Arrival.mp4'])
def test_filename_override_cannot_change_media_extension(filename):
    item=MediaItem(id='i',source_id='s',path='original.mkv',kind='movies',signature={'type':'file'},decision=MatchDecision(item_id='i',metadata={'title':'Arrival','filename':filename}))
    with pytest.raises(ValueError,match='extension'):Naming.render(item,NamingProfile())

def test_filename_override_allows_case_insensitive_original_extension():
    item=MediaItem(id='i',source_id='s',path='original.MKV',kind='movies',signature={'type':'file'},decision=MatchDecision(item_id='i',metadata={'title':'Arrival','filename':'Arrival.mkv'}))
    assert Naming.render(item,NamingProfile()).path.endswith('/Arrival.mkv')

def test_undo_with_unrecorded_directory_member_requires_recovery(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=True)
    executor=Executor(library,planner);forward=executor.execute(plan.id,1,context)
    extra=target.parent/'new-file.txt';extra.write_bytes(b'user addition')
    undo=executor.undo_plan(forward.batch_id);assert not undo.issues
    result=executor.execute(undo.id,1,context);item=library.get(plan.operations[0].item_id)
    assert result.state=='partial'
    assert result.recovery_item_ids==[item.id]
    assert source.read_bytes()==b'original media bytes' and extra.read_bytes()==b'user addition'
    assert item.status=='error' and 'recovery_note' in item.metadata
    assert set(item.metadata['recovery_paths'])=={str(source.parent),str(target.parent)}
    assert executor.execute(undo.id,1,context).state=='partial'
    extra.unlink()
    assert executor.execute(undo.id,1,context).state=='completed'
    assert library.get(item.id).status=='approved' and 'recovery_paths' not in library.get(item.id).metadata

@pytest.mark.parametrize('kind', ['organise','scan'])
def test_queued_cancel_is_nonterminal_until_scheduler_cleanup(library,kind):
    started=threading.Event();release=threading.Event();lock=threading.Lock();calls=[]
    count=1 if kind=='organise' else 3
    def work(payload,context):
        with lock:
            calls.append(payload['n'])
            if len(calls)==count:started.set()
        assert release.wait(10)
        return {'state':'completed'}
    manager=JobManager(library.store,{kind:work})
    try:
        busy=[manager.submit(kind,{'n':n}) for n in range(count)];assert started.wait(5)
        queued=manager.submit(kind,{'n':99});assert queued.state=='queued'
        assert manager.cancel(queued.id).state=='cancelling'
        with pytest.raises(ValueError):manager.retry(queued.id)
        release.set();assert wait_terminal(manager,queued.id).state=='cancelled'
        assert 99 not in calls
        manager.retry(queued.id);assert wait_terminal(manager,queued.id).state=='completed'
        assert calls.count(99)==1
    finally:release.set();manager.shutdown()

def test_undo_activity_has_distinct_action_and_batch_identity(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    executor=Executor(library,planner);forward=executor.execute(plan.id,1,context)
    undo=executor.undo_plan(forward.batch_id);restored=executor.execute(undo.id,1,context)
    with library.store.transaction() as conn:
        rows=conn.execute('SELECT action,detail,status FROM orion_activity ORDER BY id').fetchall()
    assert [r['action'] for r in rows]==['organisation','undo']
    assert json.loads(rows[-1]['detail'])['batch_id']==restored.batch_id
    assert json.loads(rows[-1]['detail'])['undo_batch_id']==forward.batch_id

def test_anidb_provider_test_transport_failure_updates_health(tmp_path,context,monkeypatch):
    cfg=Config(tmp_path);cfg.set_pref('provider_health_anidb',{'health':'connected'})
    def offline(*a,**k):raise requests.Timeout('private-url')
    monkeypatch.setattr('orion.anidb_titles.requests.get',offline)
    runtime=Services(cfg,None,None,None,Providers(cfg),None,None)
    with pytest.raises(ProviderError) as exc:runtime.test_provider({'provider':'anidb'},context)
    assert exc.value.code=='provider_unavailable'
    assert cfg.get_pref('provider_health_anidb')=={'health':'unavailable','detail':'provider_unavailable'}
