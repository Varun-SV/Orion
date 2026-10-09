import json
import threading
from pathlib import Path
import pytest
from orion.discovery import Discovery
from orion.executor import Executor
from orion.jobs import JobManager
from orion.models import MatchDecision
from orion.naming import NamingProfile
from orion.planner import PlanOptions
from test_jobs import wait_terminal
from test_sidecars import enabled_plan
from tests_support import make_plan

@pytest.mark.parametrize('indexed',[False,True])
def test_undo_rejects_a_new_arrival_in_original_directory(library,tmp_path,context,indexed):
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=True)
    executor=Executor(library,planner);forward=executor.execute(plan.id,1,context)
    source.parent.mkdir();arrival=source.parent/'new-arrival.mkv';arrival.write_bytes(b'new arrival')
    if indexed:Discovery(library).scan([library.get(plan.operations[0].item_id).source_id],False,context)
    undo=executor.undo_plan(forward.batch_id)
    assert any(i.code in ('restore_directory_populated','restore_item_conflict') for i in undo.issues)
    with pytest.raises(ValueError):executor.execute(undo.id,1,context)
    assert target.read_bytes()==b'original media bytes' and arrival.read_bytes()==b'new arrival'
    assert not source.exists()


def test_undo_rechecks_restore_contents_after_preview(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=True)
    executor=Executor(library,planner);forward=executor.execute(plan.id,1,context)
    undo=executor.undo_plan(forward.batch_id);assert not undo.issues
    source.parent.mkdir();arrival=source.parent/'new.txt';arrival.write_bytes(b'keep')
    with pytest.raises(ValueError,match='restore'):executor.execute(undo.id,1,context)
    assert target.read_bytes()==b'original media bytes' and arrival.read_bytes()==b'keep'


def test_undo_keeps_sidecars_when_all_media_are_excluded(library,tmp_path,context):
    planner,plan,source=enabled_plan(library,tmp_path,context)
    executor=Executor(library,planner);forward=executor.execute(plan.id,1,context)
    moves=[op.id for op in executor.operations(plan.id) if op.kind=='move']
    sidecar=next(Path(op.destination) for op in plan.operations if op.kind=='create_nfo');before=sidecar.read_bytes()
    undo=executor.undo_plan(forward.batch_id,moves)
    assert not any(op.kind=='remove_created' for op in undo.operations)
    assert any(w.code=='sidecar_retained_for_excluded_media' for w in undo.warnings)
    assert executor.execute(undo.id,1,context).state=='partial'
    assert sidecar.read_bytes()==before and not source.exists()


def test_undo_keeps_shared_sidecar_for_one_excluded_directory_member(library,tmp_path,context):
    planner,base,source,target=make_plan(library,tmp_path,context,directory=True)
    with library.store.transaction() as conn:did=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan=planner.create([base.operations[0].item_id],PlanOptions(destination_id=did,profile=NamingProfile(nfo_enabled=True)))
    executor=Executor(library,planner);forward=executor.execute(plan.id,1,context)
    media=next(op for op in executor.operations(plan.id) if op.source==str(source))
    sidecar=next(Path(op.destination) for op in plan.operations if op.kind=='create_nfo');before=sidecar.read_bytes()
    undo=executor.undo_plan(forward.batch_id,[media.id])
    assert not any(op.kind=='remove_created' for op in undo.operations)
    assert executor.execute(undo.id,1,context).state=='partial'
    assert target.read_bytes()==b'original media bytes' and sidecar.read_bytes()==before
    assert source.with_suffix('.en.srt').read_bytes()==b'subtitle'

@pytest.mark.parametrize('clear',[False,True])
@pytest.mark.parametrize('directory',[False,True])
def test_active_execution_blocks_decision_mutation(library,tmp_path,context,clear,directory):
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=directory)
    iid=plan.operations[0].item_id;before=library.get(iid).decision
    moved=threading.Event();release=threading.Event()
    class Hold(Executor):
        held=False
        def _journal(self,op,state,**details):
            super()._journal(op,state,**details)
            if state=='completed' and not self.held:
                self.held=True;moved.set();assert release.wait(5)
    executor=Hold(library,planner)
    manager=JobManager(library.store,{'organise':lambda p,c:executor.execute(plan.id,1,c)})
    try:
        job=manager.submit('organise',{'plan_id':plan.id,'revision':1});assert moved.wait(3)
        with pytest.raises(ValueError,match='active|running|execut'):
            if clear:library.clear_decision(iid)
            else:library.decide(iid,MatchDecision(item_id=iid,metadata={'title':'Replacement'}))
        assert library.get(iid).decision==before
        release.set();assert wait_terminal(manager,job.id).state=='completed'
        assert library.get(iid).decision==before and library.get(iid).status=='organised'
    finally:release.set();manager.shutdown()


def test_retry_scan_rejects_source_paused_after_failure(library,tmp_path,context):
    root=tmp_path/'source';root.mkdir();sid=library.add_source(root)['id'];attempts=[]
    def scan(payload,job_context):
        attempts.append(1)
        if len(attempts)==1:raise ValueError('fixture failure')
        return Discovery(library).scan(payload['source_ids'],False,job_context)
    manager=JobManager(library.store,{'scan':scan})
    try:
        job=manager.submit('scan',{'source_ids':[sid],'deep':False});assert wait_terminal(manager,job.id).state=='failed'
        with library.store.transaction() as conn:conn.execute('INSERT OR REPLACE INTO orion_settings VALUES(?,?)',('source_archived_'+sid,'true'))
        (root/'new.mkv').write_bytes(b'keep')
        with pytest.raises(ValueError,match='active|paused|archiv'):manager.retry(job.id)
        assert attempts==[1] and library.query().items==[] and manager.get(job.id).state=='failed'
    finally:manager.shutdown()


def test_discovery_skips_a_source_paused_after_queueing(library,tmp_path,context):
    root=tmp_path/'source';root.mkdir();sid=library.add_source(root)['id'];(root/'new.mkv').write_bytes(b'keep')
    with library.store.transaction() as conn:conn.execute('INSERT OR REPLACE INTO orion_settings VALUES(?,?)',('source_archived_'+sid,'true'))
    result=Discovery(library).scan([sid],False,context)
    assert result.processed==0 and library.query().items==[]


def test_undo_refuses_an_unreadable_restore_directory(library,tmp_path,context,monkeypatch):
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=True)
    executor=Executor(library,planner);forward=executor.execute(plan.id,1,context)
    undo=executor.undo_plan(forward.batch_id);source.parent.mkdir()
    def unreadable(*args,onerror=None,**kwargs):
        if onerror:onerror(OSError('cannot enumerate restore root'))
        return iter(())
    monkeypatch.setattr('orion.executor.os.walk',unreadable)
    assert any(i.code=='restore_directory_populated' for i in executor._restore_conflicts(undo,undo.operations))


def test_partial_undo_retry_accepts_only_its_owned_restored_members(library,tmp_path,context):
    from orion.filesystem import Filesystem
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=True)
    executor=Executor(library,planner);forward=executor.execute(plan.id,1,context);undo=executor.undo_plan(forward.batch_id)
    class FailMediaOnce(Filesystem):
        fail=True
        def rename_noreplace(self,src,dst):
            if Path(src).suffix=='.mkv' and self.fail:
                self.fail=False;raise OSError('temporary fixture failure')
            return super().rename_noreplace(src,dst)
    executor=Executor(library,planner,FailMediaOnce())
    assert executor.execute(undo.id,1,context).state=='partial'
    assert source.with_suffix('.en.srt').read_bytes()==b'subtitle'
    assert executor.execute(undo.id,1,context).state=='completed'
    assert source.read_bytes()==b'original media bytes'
    assert library.get(plan.operations[0].item_id).status=='approved'


def test_active_execution_keeps_other_items_editable(library,tmp_path,context):
    from orion.models import MediaItem
    from orion.discovery import signature
    planner,plan,source,target=make_plan(library,tmp_path,context)
    item=library.get(plan.operations[0].item_id)
    other_path=source.parent/'Other.mkv';other_path.write_bytes(b'other')
    library.upsert(MediaItem(id='other',source_id=item.source_id,path=str(other_path),kind='movies',signature=signature(other_path)))
    moved=threading.Event();release=threading.Event()
    class Hold(Executor):
        def _journal(self,op,state,**details):
            super()._journal(op,state,**details)
            if state=='completed':moved.set();assert release.wait(5)
    executor=Hold(library,planner)
    manager=JobManager(library.store,{'organise':lambda p,c:executor.execute(plan.id,1,c)})
    try:
        job=manager.submit('organise',{'plan_id':plan.id});assert moved.wait(3)
        assert library.decide('other',MatchDecision(item_id='other',metadata={'title':'Other'})).status=='approved'
        release.set();assert wait_terminal(manager,job.id).state=='completed'
    finally:release.set();manager.shutdown()


def test_resumed_source_scan_retry_runs_normally(library,tmp_path,context):
    root=tmp_path/'source';root.mkdir();sid=library.add_source(root)['id'];attempts=[]
    def scan(payload,job_context):
        attempts.append(1)
        if len(attempts)==1:raise ValueError('fixture failure')
        return Discovery(library).scan([sid],False,job_context)
    manager=JobManager(library.store,{'scan':scan})
    try:
        job=manager.submit('scan',{'source_ids':[sid]});assert wait_terminal(manager,job.id).state=='failed'
        with library.store.transaction() as conn:conn.execute('INSERT OR REPLACE INTO orion_settings VALUES(?,?)',('source_archived_'+sid,'true'))
        with pytest.raises(ValueError):manager.retry(job.id)
        with library.store.transaction() as conn:conn.execute('DELETE FROM orion_settings WHERE key=?',('source_archived_'+sid,))
        (root/'new.mkv').write_bytes(b'keep')
        manager.retry(job.id);assert wait_terminal(manager,job.id).state=='completed'
        assert attempts==[1,1] and library.query().total==1
    finally:manager.shutdown()
