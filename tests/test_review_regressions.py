from pathlib import Path
import os
import pytest
from tests_support import make_plan, Crash
from orion.discovery import Discovery, signature
from orion.executor import Executor
from orion.filesystem import Filesystem
from orion.models import MatchDecision
from orion.planner import Planner, PlanOptions
from orion.naming import NamingProfile


def test_new_arrival_at_retired_path_gets_new_identity(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    old_id=plan.operations[0].item_id
    Executor(library,planner).execute(plan.id,1,context)
    source.write_bytes(b'a different arrival')
    sid=library.sources()[0]['id']
    assert Discovery(library).scan([sid],False,context).processed==1
    assert library.query().total==2
    incoming=next(i for i in library.query().items if i.path==str(source))
    assert incoming.id!=old_id and incoming.decision is None
    assert library.get(old_id).path==str(target)
    assert Discovery(library).scan([sid],False,context).unchanged==1
    assert library.query().total==2


@pytest.mark.parametrize('kind,ext',[('books','.pdf'),('music','.flac')])
def test_in_place_rescan_retains_identity(library,tmp_path,context,kind,ext):
    root=tmp_path/'incoming';root.mkdir();source=root/('original'+ext);source.write_bytes(b'fixture')
    sid=library.add_source(root,kind=kind)['id'];Discovery(library).scan([sid],False,context)
    item=library.query().items[0]
    library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Renamed','author':'Author','artist':'Artist','album':'Album','track_number':'1'}))
    planner=Planner(library);plan=planner.create([item.id],PlanOptions(in_place=True))
    assert not plan.issues
    Executor(library,planner).execute(plan.id,1,context)
    assert Discovery(library).scan([sid],False,context).unchanged==1
    assert library.query().total==1 and library.get(item.id).status=='organised'


def test_stale_scan_during_move_does_not_create_ghost(library,tmp_path,context,monkeypatch):
    import orion.discovery as discovery
    planner,plan,source,target=make_plan(library,tmp_path,context)
    original=discovery.parsed_metadata
    def move_during_read(path,kind):
        metadata=original(path,kind)
        Executor(library,planner).execute(plan.id,1,context)
        return metadata
    monkeypatch.setattr(discovery,'parsed_metadata',move_during_read)
    Discovery(library).scan([library.sources()[0]['id']],True,context)
    assert library.query().total==1 and library.query().items[0].path==str(target)


def loose_plan(library,tmp_path,context):
    planner,initial,source,target=make_plan(library,tmp_path,context)
    sub=source.with_suffix('.srt');sub.write_bytes(b'subtitle')
    with library.store.transaction() as conn:did=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan=planner.create([initial.operations[0].item_id],PlanOptions(destination_id=did))
    return planner,plan,source,target,sub,did


@pytest.mark.parametrize('edit_primary',[False,True])
def test_loose_companion_retry_validates_moved_primary(library,tmp_path,context,edit_primary):
    planner,plan,source,target,sub,_=loose_plan(library,tmp_path,context)
    class Once(Filesystem):
        failed=False
        def rename_noreplace(self,src,dst):
            if Path(src).suffix=='.srt' and not self.failed:
                self.failed=True;raise OSError('transient subtitle failure')
            return super().rename_noreplace(src,dst)
    executor=Executor(library,planner,Once())
    assert executor.execute(plan.id,1,context).state=='partial'
    if edit_primary:
        target.write_bytes(b'user edit')
        with pytest.raises(ValueError,match='target_changed'):executor.execute(plan.id,1,context)
        assert sub.read_bytes()==b'subtitle' and target.read_bytes()==b'user edit'
    else:
        source.write_bytes(b'new arrival must stay')
        assert executor.execute(plan.id,1,context).state=='completed'
        assert target.read_bytes()==b'original media bytes' and source.read_bytes()==b'new arrival must stay'
        assert not sub.exists() and target.with_suffix('.srt').read_bytes()==b'subtitle'


@pytest.mark.parametrize('directory',[False,True])
def test_skip_conflict_never_attaches_optional_files_to_existing_item(library,tmp_path,context,directory):
    if directory:
        planner,initial,source,target=make_plan(library,tmp_path,context,directory=True)
        target.parent.mkdir(parents=True);target.write_bytes(b'unrelated existing film')
        with library.store.transaction() as conn:did=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    else:
        planner,initial,source,target,sub,did=loose_plan(library,tmp_path,context)
        target.parent.mkdir(parents=True);target.write_bytes(b'unrelated existing film')
    plan=planner.create([initial.operations[0].item_id],PlanOptions(destination_id=did,conflict='skip',profile=NamingProfile(nfo_enabled=True)))
    assert not plan.operations
    assert any(w.code=='item_skipped' for w in plan.warnings)
    assert source.read_bytes()==b'original media bytes' and target.read_bytes()==b'unrelated existing film'
    assert library.get(initial.operations[0].item_id).status=='approved'


@pytest.mark.parametrize('boundary',['cancel_verify','crash_metadata'])
def test_copy_metadata_recovery_preserves_owned_verified_temp(library,tmp_path,context,monkeypatch,boundary):
    import orion.filesystem as filesystem
    planner,initial,source,target=make_plan(library,tmp_path,context)
    os.utime(source,ns=(1234567890000000000,1234567890000000000))
    item=library.get(initial.operations[0].item_id);item.signature=signature(source);library.upsert(item)
    with library.store.transaction() as conn:did=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan=planner.create([item.id],PlanOptions(destination_id=did))
    class Cross(Filesystem):
        def same_volume(self,*args):return False
    executor=Executor(library,planner,Cross())
    if boundary=='crash_metadata':
        original=filesystem.shutil.copystat
        def crash_after_metadata(*args,**kwargs):
            original(*args,**kwargs);raise Crash()
        monkeypatch.setattr(filesystem.shutil,'copystat',crash_after_metadata)
        with pytest.raises(Crash):executor.execute(plan.id,1,context)
        monkeypatch.setattr(filesystem.shutil,'copystat',original)
    else:
        class CancelAtVerify:
            stop=False
            def cancelled(self):return self.stop
            def progress(self,phase,*args):
                if phase=='Verifying copy':self.stop=True
        assert executor.execute(plan.id,1,CancelAtVerify()).state=='cancelled'
    temp=target.parent/('.orion-'+plan.operations[0].id+'.part');inode=temp.stat().st_ino
    assert source.read_bytes()==temp.read_bytes()==b'original media bytes'
    assert Executor(library,planner,Cross()).execute(plan.id,1,context).state=='completed'
    assert target.stat().st_ino==inode and target.read_bytes()==b'original media bytes'


@pytest.mark.parametrize('conflict',['edited','occupied'])
def test_explicit_undo_exclusion_restores_safe_members(library,tmp_path,context,conflict):
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=True)
    executor=Executor(library,planner);result=executor.execute(plan.id,1,context)
    primary=next(op for op in plan.operations if op.source==str(source))
    if conflict=='edited':target.write_bytes(b'user edit')
    else:source.parent.mkdir(parents=True);source.write_bytes(b'new original occupant')
    blocked=executor.undo_plan(result.batch_id)
    assert blocked.issues
    undo=executor.undo_plan(result.batch_id,exclude_operation_ids=[primary.id])
    if conflict=='occupied':
        # A new directory arrival owns the whole restore location, even when
        # its conflicting media operation has been explicitly excluded.
        assert any(issue.code=='restore_directory_populated' for issue in undo.issues)
        with pytest.raises(ValueError):executor.execute(undo.id,1,context)
        assert source.read_bytes()==b'new original occupant'
        assert target.read_bytes()==b'original media bytes'
        assert not source.with_name('original.en.srt').exists()
        return
    assert not undo.issues and len(undo.operations)==1
    assert undo.excluded_operation_ids==[primary.id]
    assert any(w.operation_id==primary.id for w in undo.warnings)
    restored=executor.execute(undo.id,1,context)
    assert restored.state=='partial' and restored.skipped_operation_ids==[primary.id]
    assert source.with_name('original.en.srt').read_bytes()==b'subtitle'
    assert target.read_bytes()==(b'user edit' if conflict=='edited' else b'original media bytes')
    assert library.get(primary.item_id).path==str(target.parent)
    assert library.get(primary.item_id).status=='error'

def test_copy_metadata_recovery_refuses_changed_temporary_content(library,tmp_path,context,monkeypatch):
    import orion.filesystem as filesystem
    planner,plan,source,target=make_plan(library,tmp_path,context)
    class Cross(Filesystem):
        def same_volume(self,*args):return False
    original=filesystem.shutil.copystat
    def crash(*args,**kwargs):original(*args,**kwargs);raise Crash()
    monkeypatch.setattr(filesystem.shutil,'copystat',crash)
    with pytest.raises(Crash):Executor(library,planner,Cross()).execute(plan.id,1,context)
    monkeypatch.setattr(filesystem.shutil,'copystat',original)
    temp=target.parent/('.orion-'+plan.operations[0].id+'.part')
    temp.write_bytes(b'x'*len(b'original media bytes'))
    assert Executor(library,planner,Cross()).execute(plan.id,1,context).state=='failed'
    assert temp.read_bytes()==b'x'*len(b'original media bytes')
    assert source.read_bytes()==b'original media bytes' and not target.exists()


def test_partial_inverse_loose_batch_can_retry(library,tmp_path,context):
    planner,plan,source,target,sub,_=loose_plan(library,tmp_path,context)
    executor=Executor(library,planner);result=executor.execute(plan.id,1,context)
    undo=executor.undo_plan(result.batch_id)
    class Once(Filesystem):
        failed=False
        def rename_noreplace(self,src,dst):
            if Path(src).suffix=='.srt' and not self.failed:
                self.failed=True;raise OSError('transient failure')
            return super().rename_noreplace(src,dst)
    inverse=Executor(library,planner,Once())
    assert inverse.execute(undo.id,1,context).state=='partial'
    assert inverse.execute(undo.id,1,context).state=='completed'
    assert source.read_bytes()==b'original media bytes' and sub.read_bytes()==b'subtitle'


def test_partial_undo_with_companion_excluded_indexes_restored_primary(library,tmp_path,context):
    planner,plan,source,target,sub,_=loose_plan(library,tmp_path,context)
    executor=Executor(library,planner);result=executor.execute(plan.id,1,context)
    companion=next(op for op in plan.operations if op.source==str(sub))
    undo=executor.undo_plan(result.batch_id,exclude_operation_ids=[companion.id])
    assert executor.execute(undo.id,1,context).state=='partial'
    item=library.get(plan.operations[0].item_id)
    assert item.path==str(source) and item.status=='error'
    assert source.read_bytes()==b'original media bytes' and target.with_suffix('.srt').read_bytes()==b'subtitle'
