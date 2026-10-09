import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from orion.app import create_app
from orion.config import Config
from orion.discovery import Discovery,signature
from orion.duplicates import Duplicates
from orion.executor import Executor
from orion.filesystem import Filesystem
from orion.models import MediaItem,MatchDecision
from orion.naming import Naming,NamingProfile,valid_relative
from orion.planner import PlanOptions
from orion.services import Services
from tests_support import make_plan,Crash
from test_api import client


def test_destination_rejects_an_ordinary_child_of_a_link(client,tmp_path):
    root=tmp_path/'media';(root/'library').mkdir(parents=True)
    assert client.post('/api/v1/sources',json={'path':str(root)}).status_code==201
    alias=tmp_path/'alias'
    if os.name=='nt':
        import _winapi
        _winapi.CreateJunction(str(root),str(alias))
    else:alias.symlink_to(root,target_is_directory=True)
    try:
        response=client.post('/api/v1/destinations',json={'path':str(alias/'library')})
        assert response.status_code==400
        assert client.get('/api/v1/destinations').json()==[]
    finally:alias.rmdir() if os.name=='nt' else alias.unlink()

@pytest.mark.parametrize('kind,ext',[('movies','.mkv'),('series','.mp4'),('music','.flac'),('books','.epub')])
@pytest.mark.parametrize('template',['{title}','{title}.txt'])
def test_rendered_templates_preserve_media_suffix(kind,ext,template):
    item=MediaItem(id='a',source_id='s',path='original'+ext,kind=kind,signature={'type':'file'},decision=MatchDecision(item_id='a',metadata={'title':'Example','episode':2}))
    profile=NamingProfile(movie_template=template,episode_template=template,music_template=template,book_template=template)
    with pytest.raises(ValueError,match='extension'):Naming.render(item,profile)

@pytest.mark.parametrize('char',['<','>','"','|','?','*',chr(1),chr(31)])
def test_portable_components_reject_windows_invalid_characters(char):
    with pytest.raises(ValueError,match='portable'):valid_relative('Movies'+char+'/Example.mkv')


def test_undo_preview_is_stale_after_original_companions_complete(library,tmp_path,context):
    planner,initial,source,target=make_plan(library,tmp_path,context)
    subtitle=source.with_suffix('.srt');subtitle.write_bytes(b'subtitle')
    with library.store.transaction() as conn:did=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan=planner.create([initial.operations[0].item_id],PlanOptions(destination_id=did))
    class FailSubtitle(Filesystem):
        fail=True
        def rename_noreplace(self,src,dst):
            if Path(src)==subtitle and self.fail:
                self.fail=False
                raise OSError('fixture unavailable')
            return super().rename_noreplace(src,dst)
    executor=Executor(library,planner,FailSubtitle())
    partial=executor.execute(plan.id,1,context);assert partial.state=='partial'
    old_undo=executor.undo_plan(partial.batch_id);assert len(old_undo.operations)==1
    assert executor.execute(plan.id,1,context).state=='completed'
    organised_subtitle=target.with_suffix('.srt')
    with pytest.raises(ValueError,match='stale'):executor.execute(old_undo.id,1,context)
    assert target.read_bytes()==b'original media bytes' and organised_subtitle.read_bytes()==b'subtitle'
    fresh=executor.undo_plan(partial.batch_id)
    assert executor.execute(fresh.id,1,context).state=='completed'
    assert source.read_bytes()==b'original media bytes' and subtitle.read_bytes()==b'subtitle'


def test_lookup_cannot_publish_candidates_for_replaced_media(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    original=library.get(plan.operations[0].item_id)
    class LateCandidate:
        changed=False
        def model_dump(self):
            if not self.changed:
                self.changed=True
                source.write_bytes(b'new arrival content')
                library.discovered(original.model_copy(update={'signature':signature(source),'decision':None,'metadata':{'title':'New arrival'}}))
            return {'provider':'tmdb','provider_id':'old','title':'Old media','metadata':{},'evidence':[]}
    runtime=Services(Config(tmp_path/'preferences'),library.store,library,None,SimpleNamespace(candidates=lambda *a,**k:[LateCandidate()]),planner,None)
    from orion.providers import ProviderError
    with pytest.raises(ProviderError) as error:runtime.lookup({'item_id':original.id},context)
    assert error.value.code=='item_changed'
    current=library.get(original.id)
    assert current.metadata=={'title':'New arrival'} and current.status=='pending' and current.decision is None

@pytest.mark.parametrize('provider',['tmdb','anilist','anidb'])
def test_episode_comparison_separates_numbers_and_groups_same_episode(library,tmp_path,context,provider):
    root=tmp_path/'episodes';root.mkdir();sid=library.add_source(root,kind='series')['id']
    items=[]
    for index,episode in enumerate([1,2,1]):
        file=root/(str(index)+'.mkv');file.write_bytes(str(index).encode())
        item=MediaItem(id=str(index),source_id=sid,path=str(file),kind='series',signature=signature(file),metadata={'season':1,'episode':episode},decision=MatchDecision(item_id=str(index),provider=provider,provider_id='show',metadata={'title':'Show'}))
        library.upsert(item);items.append(item)
    result=Duplicates(library).compare([i.id for i in items],False,context)
    assert [g.item_ids for g in result.version_groups]==[['0','2']]

@pytest.mark.parametrize('after_batch',[False,True])
def test_startup_finishes_completed_operations_and_interrupted_job(library,tmp_path,context,after_batch):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    class CrashBeforeItem(Executor):
        def _update_items_and_directories(self,operations):raise Crash()
    if after_batch:Executor(library,planner).execute(plan.id,1,context)
    else:
        with pytest.raises(Crash):CrashBeforeItem(library,planner).execute(plan.id,1,context)
    iid=plan.operations[0].item_id
    assert target.is_file() and not source.exists()
    with library.store.transaction() as conn:
        conn.execute("INSERT INTO orion_jobs(id,kind,state,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)",('interrupted-forward','organise','running',json.dumps({'plan_id':plan.id,'revision':1}),'now','now'))
    import shutil
    shutil.copyfile(library.store.path,library.store.path.parent/'organizer.db')
    with TestClient(create_app(library.store.path.parent),base_url='http://127.0.0.1:4321') as browser:
        runtime=browser.app.state.services
        for _ in range(100):
            if runtime.jobs.get('interrupted-forward').state=='completed':break
            time.sleep(.02)
        item=runtime.library.get(iid)
        assert item.path==str(target) and item.status=='organised'
        job=runtime.jobs.get('interrupted-forward')
        assert job.state=='completed' and job.result['state']=='completed'
        with runtime.store.transaction() as conn:
            batch=conn.execute('SELECT state FROM orion_batches WHERE plan_id=?',(plan.id,)).fetchone()
            assert batch[0]=='completed'
            assert conn.execute("SELECT COUNT(*) FROM orion_activity WHERE action='organisation'").fetchone()[0]==1
        runtime.executor.reconcile()
        with runtime.store.transaction() as conn:
            assert conn.execute("SELECT COUNT(*) FROM orion_activity WHERE action='organisation'").fetchone()[0]==1
        assert target.read_bytes()==b'original media bytes'


def test_no_match_publication_keeps_a_confirmation_made_during_lookup(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    iid=plan.operations[0].item_id;library.clear_decision(iid)
    def candidates(*args,**kwargs):
        library.decide(iid,MatchDecision(item_id=iid,metadata={'title':'Confirmed during request'}))
        return []
    runtime=Services(Config(tmp_path/'prefs'),library.store,library,None,SimpleNamespace(candidates=candidates),planner,None)
    assert runtime.lookup({'item_id':iid},context)['candidates']==[]
    current=library.get(iid)
    assert current.status=='approved' and current.decision.metadata['title']=='Confirmed during request'


def test_recovery_does_not_finalize_changed_completed_destination(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    class CrashBeforeItem(Executor):
        def _update_items_and_directories(self,operations):raise Crash()
    with pytest.raises(Crash):CrashBeforeItem(library,planner).execute(plan.id,1,context)
    target.write_bytes(b'external edit')
    result=Executor(library,planner).reconcile()
    assert result.recovered_batch_ids==[] and result.review_operation_ids==[plan.operations[0].id]
    assert library.get(plan.operations[0].item_id).path==str(source)
    assert target.read_bytes()==b'external edit'
    with library.store.transaction() as conn:assert conn.execute('SELECT state FROM orion_batches').fetchone()[0]=='running'


def test_matching_template_suffix_and_directory_layout_remain_valid():
    item=MediaItem(id='a',source_id='s',path='a.mkv',kind='movies',signature={'type':'file'},decision=MatchDecision(item_id='a',metadata={'title':'Film'}))
    assert Naming.render(item,NamingProfile(movie_template='{title}.MKV')).path=='Film.MKV'
    folder=item.model_copy(update={'path':'Folder','signature':{'type':'directory'}})
    assert Naming.render(folder,NamingProfile(folder_template='{title}')).path=='Film'


def test_whole_series_comparison_uses_show_identity():
    item=MediaItem(id='a',source_id='s',path='Show',kind='series',signature={'type':'directory'},decision=MatchDecision(item_id='a',provider='tmdb',provider_id='show',metadata={'title':'Show','episode':1}))
    identity,_=Duplicates._identity(item,item.decision.metadata)
    other=item.model_copy(update={'decision':item.decision.model_copy(update={'metadata':{'title':'Show','episode':2}})})
    assert Duplicates._identity(other,other.decision.metadata)[0]==identity
