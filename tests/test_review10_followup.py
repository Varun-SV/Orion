"""Regressions for the seven review findings on Orion PR #3."""
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orion.config import Config
from orion.discovery import Discovery
from orion.executor import Executor
from orion.integrations.manager import ServerIntegration, ServerSettings
from orion.library import Library
from orion.models import MatchDecision
from orion.naming import NamingProfile
from orion.planner import PlanOptions
from orion.providers import ProviderError
from orion.services import Services
from tests_support import make_plan
from test_api import client


def test_mapping_persisted_identity_survives_restart_and_credentials_rotate(library, tmp_path):
    directory=tmp_path/'prefs'
    config=Config(directory)
    config.set_api_key('media_server','same-key')
    first=ServerIntegration(SimpleNamespace(config=config,store=library.store,providers=None))
    first.save(ServerSettings(enabled=True,url='http://127.0.0.1:8096',user_id='chosen'))
    stable=first.mapping_revision()
    transient=first.revision()
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_settings(key,value) VALUES(?,?)',
                     ('server_mapping_'+stable+'_show',json.dumps({'provider_id':'1','confirmed':True})))
    restored=ServerIntegration(SimpleNamespace(config=Config(directory),store=library.store,providers=None))
    assert restored.mapping_revision()==stable
    assert restored.revision()!=transient
    with library.store.transaction() as conn:
        assert conn.execute('SELECT value FROM orion_settings WHERE key=?',
                            ('server_mapping_'+restored.mapping_revision()+'_show',)).fetchone() is not None
    restored.runtime.config.set_api_key('media_server','replacement')
    assert restored.revision()!=transient and restored.mapping_revision()==stable


def test_api_confirmation_rejects_stale_media_snapshot(client,tmp_path,context):
    root=tmp_path/'incoming';root.mkdir()
    file=root/'Arrival.mkv';file.write_bytes(b'old content')
    runtime=client.app.state.services
    sid=runtime.library.add_source(root,kind='movies')['id']
    Discovery(runtime.library).scan([sid],False,context)
    previous=runtime.library.query().items[0]
    file.write_bytes(b'new, entirely different media bytes')
    Discovery(runtime.library).scan([sid],False,context)
    stale=client.put('/api/v1/items/'+previous.id+'/decision',
                     json={'item_id':previous.id,'signature_token':previous.signature_token,
                           'metadata':{'title':'Old film'}})
    assert stale.status_code in (400,409)
    current=runtime.library.get(previous.id)
    assert current.decision is None and current.signature != previous.signature
    assert client.put('/api/v1/items/'+previous.id+'/decision',
                      json={'item_id':previous.id,'metadata':{'title':'Old film'}}).status_code==422
    fresh=client.put('/api/v1/items/'+previous.id+'/decision',
                     json={'item_id':previous.id,'signature_token':current.signature_token,
                           'metadata':{'title':'Current film'}})
    assert fresh.status_code==200
    assert runtime.library.get(previous.id).decision.metadata['title']=='Current film'


@pytest.mark.parametrize('old_failure',[False,True])
def test_overlapping_lookup_last_submitted_wins(library,tmp_path,context,old_failure):
    planner, plan, source, target=make_plan(library,tmp_path,context)
    iid=plan.operations[0].item_id
    library.clear_decision(iid)
    started=threading.Event()
    release=threading.Event()
    def candidates(item,ctx,provider=None):
        if threading.current_thread().name == 'old-lookup':
            started.set()
            assert release.wait(5)
            if old_failure: raise ProviderError('provider_unavailable','tmdb')
            return []
        return [SimpleNamespace(model_dump=lambda: {'title':'New result','provider':'tmdb'})]
    services=Services(Config(tmp_path/'lookup-prefs'),library.store,library,None,
                      SimpleNamespace(candidates=candidates),None,None)
    results=[]
    def old():
        try:results.append(services.lookup({'item_id':iid},context))
        except ProviderError:results.append('old_failed')
    worker=threading.Thread(target=old,name='old-lookup')
    worker.start()
    try:
        assert started.wait(5)
        newer=services.lookup({'item_id':iid},context)
        assert newer['candidates'][0]['title']=='New result'
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    item=library.get(iid)
    assert item.metadata['candidates'][0]['title']=='New result'
    assert item.metadata['lookup_state']=='ready'
    assert item.status=='pending'
    if not old_failure:
        assert results[0]['skipped'] is True


def test_revalidated_plan_rejects_replaced_destination_volume(library,tmp_path,context,monkeypatch):
    import orion.planner as planning
    planner,plan,source,target=make_plan(library,tmp_path,context)
    destination=Path(plan.operations[0].verification['destination_root'])
    identity=planning.volume_identity
    def replaced(root):
        value=identity(root)
        return ['new-volume',*value] if Path(root)==destination else value
    monkeypatch.setattr(planning,'volume_identity',replaced)
    checked=planner.validate(plan.id,plan.revision)
    assert 'volume_changed' in [i.code for i in checked.issues]
    with pytest.raises(ValueError):
        Executor(library,planner).execute(plan.id,plan.revision,context)
    assert source.exists() and not target.exists()


def test_undo_passes_successful_batch_through_server_refresh(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    executor=Executor(library,planner)
    assert executor.execute(plan.id,1,context).state=='completed'
    with library.store.transaction() as conn:
        forward=conn.execute('SELECT id FROM orion_batches WHERE plan_id=?',(plan.id,)).fetchone()['id']
    undo=executor.undo_plan(forward)
    seen=[]
    server=SimpleNamespace(after_local_success=lambda result: (seen.append(result.batch_id) or result.model_dump()))
    services=Services(Config(tmp_path/'prefs'),library.store,library,None,None,planner,executor,server=server)
    result=services.handlers()['undo']({'plan_id':undo.id,'revision':undo.revision},context)
    assert result['state']=='completed'
    assert seen == [result['batch_id']]
    assert result['batch_id'] != forward
    assert source.exists() and not target.exists()


def test_kind_scoped_profile_cannot_be_applied_to_other_collection(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    with library.store.transaction() as conn:
        destination=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    custom=planner.create([plan.operations[0].item_id],PlanOptions(
        destination_id=destination,profile=NamingProfile(id='music-only',kind='music')))
    assert any(issue.code=='profile_kind_mismatch' for issue in custom.issues)
    assert not custom.operations


def test_directory_backed_movie_keeps_custom_rendered_subfolders(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=True)
    iid=plan.operations[0].item_id
    with library.store.transaction() as conn:
        destination=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    custom=planner.create([iid],PlanOptions(destination_id=destination,
        profile=NamingProfile(id='special',kind='movies',
            folder_template='{title}',movie_template='Specials/{title}{ext}')))
    movie=next(op for op in custom.operations if op.source==str(source))
    assert 'Specials' in Path(movie.destination).parts
    assert Path(movie.destination).parent.name=='Specials'
    assert not custom.issues
