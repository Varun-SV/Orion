from tests_support import make_plan
from orion.executor import Executor

def test_undo_restores_original_bytes(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    executor = Executor(library,planner)
    result = executor.execute(plan.id,1,context)
    undo = executor.undo_plan(result.batch_id)
    assert not undo.issues
    assert target.is_file() and not source.exists()
    assert executor.execute(undo.id,undo.revision,context).state == 'completed'
    assert source.read_bytes() == b'original media bytes'
    assert not target.exists()

def test_undo_preserves_changed_target(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    executor = Executor(library,planner)
    result = executor.execute(plan.id,1,context)
    target.write_bytes(b'user changes')
    undo = executor.undo_plan(result.batch_id)
    assert 'target_changed' in [i.code for i in undo.issues]
    assert target.read_bytes() == b'user changes'
    assert not source.exists()

def test_undo_does_not_overwrite_occupied_original(library,tmp_path,context):
    planner,plan,source,target = make_plan(library,tmp_path,context)
    executor = Executor(library,planner)
    result = executor.execute(plan.id,1,context)
    source.write_bytes(b'unrelated original')
    undo = executor.undo_plan(result.batch_id)
    assert 'destination_exists' in [i.code for i in undo.issues]
    assert source.read_bytes() == b'unrelated original'
    assert target.is_file()
