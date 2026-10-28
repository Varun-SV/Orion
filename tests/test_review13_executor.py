import pytest

from tests_support import make_plan
from orion.executor import Executor


def test_forward_plan_cannot_replay_after_successful_undo(library, tmp_path, context):
    planner, plan, source, target = make_plan(library, tmp_path, context)
    executor = Executor(library, planner)

    first = executor.execute(plan.id, plan.revision, context)
    assert first.state == 'completed'
    undo = executor.undo_plan(first.batch_id)
    assert executor.execute(undo.id, undo.revision, context).state == 'completed'
    restored_item = library.get(plan.operations[0].item_id)
    assert source.read_bytes() == b'original media bytes'
    assert not target.exists()
    assert restored_item.path == str(source)
    assert restored_item.status == 'approved'

    with pytest.raises(ValueError, match='already been undone|already completed|replay|destination'):
        executor.execute(plan.id, plan.revision, context)

    assert source.read_bytes() == b'original media bytes'
    assert not target.exists()
    restored_item = library.get(plan.operations[0].item_id)
    assert restored_item.path == str(source)
    assert restored_item.status == 'approved'


def test_forward_plan_cannot_replay_after_undo_even_if_target_is_hardlinked(library, tmp_path, context):
    planner, plan, source, target = make_plan(library, tmp_path, context)
    executor = Executor(library, planner)

    first = executor.execute(plan.id, plan.revision, context)
    undo = executor.undo_plan(first.batch_id)
    assert executor.execute(undo.id, undo.revision, context).state == 'completed'
    assert source.is_file() and not target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.hardlink_to(source)

    with pytest.raises(ValueError, match='already been undone'):
        executor.execute(plan.id, plan.revision, context)

    assert source.read_bytes() == b'original media bytes'
    assert target.read_bytes() == b'original media bytes'
    assert source.stat().st_ino == target.stat().st_ino
