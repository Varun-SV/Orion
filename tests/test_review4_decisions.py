from types import SimpleNamespace

import pytest

from orion.executor import Executor
from orion.models import MatchDecision
from orion.routes.library import overview
from tests_support import make_plan


@pytest.mark.parametrize('provider,provider_id', [('manual', ''), ('tmdb', '123')])
@pytest.mark.parametrize('directory', [False, True])
def test_reconfirming_organised_metadata_keeps_completed_move(
    library, tmp_path, context, provider, provider_id, directory
):
    planner, plan, source, target = make_plan(library, tmp_path, context, directory=directory)
    assert Executor(library, planner).execute(plan.id, 1, context).state == 'completed'
    organised = library.get(plan.operations[0].item_id)
    assert organised.status == 'organised'
    assert target.read_bytes() == b'original media bytes'
    assert not source.exists()
    runtime = SimpleNamespace(store=library.store, library=library)
    before_counts = overview(runtime)
    assert before_counts['status_counts'] == {'organised': 1}
    assert before_counts['review'] == 0
    corrected = MatchDecision(
        item_id=organised.id,
        provider=provider,
        provider_id=provider_id,
        metadata={'title': 'Corrected film', 'year': '2020'},
    )

    result = library.decide(organised.id, corrected)

    assert result.status == 'organised'
    assert result.decision == corrected
    assert result.path == organised.path
    assert result.signature == organised.signature
    assert result.metadata == organised.metadata
    assert library.get(organised.id) == result
    assert library.query(status='organised').total == 1
    assert library.query(status='approved').total == 0
    assert overview(runtime) == before_counts
    assert target.read_bytes() == b'original media bytes'
    assert not source.exists()


@pytest.mark.parametrize('status', ['pending', 'error', 'no_match', 'unavailable', 'approved'])
def test_confirming_other_states_still_approves_metadata(library, tmp_path, context, status):
    _, plan, source, _ = make_plan(library, tmp_path, context)
    item_id = plan.operations[0].item_id
    library.clear_decision(item_id)
    before = library.status(item_id, status)
    decision = MatchDecision(item_id=item_id, metadata={'title': 'Confirmed film', 'year': '2020'})

    result = library.decide(item_id, decision)

    assert result.status == 'approved'
    assert result.decision == decision
    assert result.path == before.path
    assert result.signature == before.signature
    assert library.get(item_id) == result
    assert library.query(status='approved').total == 1
    assert library.query(status='review').total == 0
    assert source.read_bytes() == b'original media bytes'
