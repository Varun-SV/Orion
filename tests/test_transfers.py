import pytest
from tests_support import make_plan
from orion.executor import Executor
from orion.filesystem import Filesystem

@pytest.mark.parametrize('cross_volume',[False,True])
def test_verified_transfer_and_retry_preserve_bytes(library,tmp_path,context,cross_volume):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class Volume(Filesystem):
        def same_volume(self,*a): return not cross_volume
    executor = Executor(library,planner,filesystem=Volume())
    result = executor.execute(plan.id,plan.revision,context)
    assert result.state == 'completed'
    assert target.read_bytes() == b'original media bytes'
    assert not source.exists()
    again = executor.execute(plan.id,plan.revision,context)
    assert again.completed_operation_ids == result.completed_operation_ids
    assert target.read_bytes() == b'original media bytes'

def test_copy_verification_failure_preserves_original(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class Corrupt(Filesystem):
        def same_volume(self,*a): return False
        def hash(self,path,context=None):
            value = super().hash(path,context)
            return '0'*64 if str(path).endswith('.part') else value
    result = Executor(library,planner,filesystem=Corrupt()).execute(plan.id,plan.revision,context)
    assert result.state == 'failed'
    assert source.read_bytes() == b'original media bytes'
    assert not target.exists()

def test_destination_race_never_overwrites(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class Race(Filesystem):
        def rename_noreplace(self,src,dst):
            dst.write_bytes(b'unrelated destination')
            return super().rename_noreplace(src,dst)
    result = Executor(library,planner,filesystem=Race()).execute(plan.id,plan.revision,context)
    assert result.state == 'failed'
    assert source.read_bytes() == b'original media bytes'
    assert target.read_bytes() == b'unrelated destination'

def test_cancelled_copy_retains_source_and_can_retry(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class Cross(Filesystem):
        def same_volume(self,*a): return False
    class StopAfterProgress:
        stop = False
        def cancelled(self): return self.stop
        def progress(self,*a,**k): self.stop = True
    executor = Executor(library,planner,filesystem=Cross())
    result = executor.execute(plan.id,1,StopAfterProgress())
    assert result.state == 'cancelled'
    assert source.is_file()
    assert not target.exists()
    assert executor.execute(plan.id,1,context).state == 'completed'

def test_changed_source_is_rejected_before_any_move(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    source.write_bytes(b'new content')
    with pytest.raises(ValueError):
        Executor(library,planner).execute(plan.id,1,context)
    assert source.read_bytes() == b'new content'
    assert not target.exists()

def test_source_change_during_copy_preserves_new_source(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class Changed(Filesystem):
        def same_volume(self,*a): return False
        def copy(self,src,*a):
            result = super().copy(src,*a)
            src.write_bytes(b'new user content')
            return result
    assert Executor(library,planner,filesystem=Changed()).execute(plan.id,1,context).state == 'failed'
    assert source.read_bytes() == b'new user content'
    assert not target.exists()

def test_modified_finalised_destination_never_deletes_source(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    class Modified(Filesystem):
        def same_volume(self,*a): return False
        def rename_noreplace(self,src,dst):
            super().rename_noreplace(src,dst)
            dst.write_bytes(b'edited after publication')
    assert Executor(library,planner,filesystem=Modified()).execute(plan.id,1,context).state == 'failed'
    assert source.read_bytes() == b'original media bytes'
    assert target.read_bytes() == b'edited after publication'

def test_cross_volume_progress_exposes_real_verification_and_publication_stages(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    class Cross(Filesystem):
        def same_volume(self,*a):return False
    class Recorded:
        records=[]
        def cancelled(self):return False
        def progress(self,phase,*args):self.records.append((phase,source.exists(),target.exists()))
    observed=Recorded()
    result=Executor(library,planner,filesystem=Cross()).execute(plan.id,1,observed)
    assert result.state=='completed'
    phases=[record[0] for record in observed.records]
    assert phases.index('Copying') < phases.index('Verifying copy') < phases.index('Finalising') < phases.index('Verifying destination') < phases.index('Removing source')
    assert next(record for record in observed.records if record[0]=='Verifying copy')[1:]==(True,False)
    assert next(record for record in observed.records if record[0]=='Removing source')[1:]==(True,True)
