import pytest
from tests_support import make_plan,Crash
from orion.executor import Executor
from orion.filesystem import Filesystem

@pytest.mark.parametrize('cross',[False,True])
def test_crash_after_move_before_sql_completion_reconciles(library,tmp_path,context,cross):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class CrashAfterRename(Filesystem):
        def same_volume(self,*a): return not cross
        def rename_noreplace(self,src,dst):
            super().rename_noreplace(src,dst)
            raise Crash()
    with pytest.raises(Crash):
        Executor(library,planner,filesystem=CrashAfterRename()).execute(plan.id,1,context)
    assert target.is_file()
    executor = Executor(library,planner)
    report = executor.reconcile()
    assert report.recovered_operation_ids == [plan.operations[0].id]
    result = executor.execute(plan.id,1,context)
    assert result.state == 'completed'
    assert target.read_bytes() == b'original media bytes'
    assert not source.exists()

def test_partial_directory_retry_does_not_recopy_completed_file(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context,directory=True)
    class OneFailure(Filesystem):
        failed = False
        def rename_noreplace(self,src,dst):
            if str(src).endswith('.mkv') and not self.failed:
                self.failed = True
                raise OSError('fixture unavailable')
            super().rename_noreplace(src,dst)
    executor = Executor(library,planner,filesystem=OneFailure())
    first = executor.execute(plan.id,1,context)
    assert first.state == 'partial'
    assert len(first.completed_operation_ids) == 1
    assert executor.execute(plan.id,1,context).state == 'completed'
    assert target.is_file()
    assert not source.parent.exists()

@pytest.mark.parametrize('boundary',['intent','copy_start','copy_checkpoint','verified','finalised','completed'])
def test_cross_volume_journal_boundaries_recover(library,tmp_path,context,boundary):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class Cross(Filesystem):
        def same_volume(self,*a): return False
    class CrashAtJournal(Executor):
        crashed = False
        def _journal(self,op,state,**details):
            super()._journal(op,state,**details)
            match = state==boundary or boundary=='copy_start' and state=='copying' and 'temp_signature' not in details or boundary=='copy_checkpoint' and state=='copying' and details.get('bytes_done',0)>0
            if match and not self.crashed:
                self.crashed = True
                raise Crash()
    with pytest.raises(Crash):
        CrashAtJournal(library,planner,filesystem=Cross()).execute(plan.id,1,context)
    assert (source.exists() and source.read_bytes()==b'original media bytes') or (target.exists() and target.read_bytes()==b'original media bytes')
    executor = Executor(library,planner,filesystem=Cross())
    executor.reconcile()
    assert executor.execute(plan.id,1,context).state == 'completed'
    assert target.read_bytes() == b'original media bytes'
    assert not source.exists()

def test_verified_temporary_copy_is_reused_after_restart(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class BeforePublish(Filesystem):
        def same_volume(self,*a): return False
        def rename_noreplace(self,*a): raise Crash()
    with pytest.raises(Crash):
        Executor(library,planner,filesystem=BeforePublish()).execute(plan.id,1,context)
    temp = target.parent/('.orion-'+plan.operations[0].id+'.part')
    old_inode = temp.stat().st_ino
    class Reuse(Filesystem):
        def same_volume(self,*a): return False
        def copy(self,*a): pytest.fail('Verified temporary copy was copied again')
    assert Executor(library,planner,filesystem=Reuse()).execute(plan.id,1,context).state == 'completed'
    assert target.stat().st_ino == old_inode

def test_unowned_temporary_file_is_never_removed(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    target.parent.mkdir(parents=True)
    temp = target.parent/('.orion-'+plan.operations[0].id+'.part')
    temp.write_bytes(b'unrelated file')
    class Cross(Filesystem):
        def same_volume(self,*a): return False
    result = Executor(library,planner,filesystem=Cross()).execute(plan.id,1,context)
    assert result.state == 'failed'
    assert temp.read_bytes() == b'unrelated file'
    assert source.exists()

def test_keep_both_directory_version_uses_separate_folder(library,tmp_path,context):
    from orion.discovery import Discovery
    from orion.models import MatchDecision
    from orion.planner import PlanOptions
    planner,plan,source,target = make_plan(library,tmp_path,context,directory=True)
    executor = Executor(library,planner)
    assert executor.execute(plan.id,1,context).state == 'completed'
    second = tmp_path/'incoming'/'Another edition'
    second.mkdir()
    (second/'other.mkv').write_bytes(b'another edition')
    sid = library.sources()[0]['id']
    Discovery(library).scan([sid],False,context)
    item = library.query(status='pending').items[0]
    library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Arrival','year':'2016'}))
    with library.store.transaction() as conn:
        did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    separate = planner.create([item.id],PlanOptions(destination_id=did,conflict='keep_both'))
    assert not separate.issues
    assert str(tmp_path/'library'/'Movies'/'Arrival (2016) (2)') in separate.operations[0].destination
    assert executor.execute(separate.id,1,context).state == 'completed'
    assert target.read_bytes() == b'original media bytes'

def test_crash_after_source_delete_reconciles(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class CrashAfterDelete(Filesystem):
        def same_volume(self,*a): return False
        def remove_source(self,*a):
            super().remove_source(*a)
            raise Crash()
    with pytest.raises(Crash):
        Executor(library,planner,filesystem=CrashAfterDelete()).execute(plan.id,1,context)
    assert not source.exists() and target.exists()
    executor = Executor(library,planner)
    assert executor.reconcile().recovered_operation_ids == [plan.operations[0].id]
    assert executor.execute(plan.id,1,context).state == 'completed'
