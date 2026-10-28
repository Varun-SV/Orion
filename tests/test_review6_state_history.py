from pathlib import Path
from uuid import uuid4
import pytest
from orion.executor import Executor
from orion.models import MatchDecision, Operation, OperationPlan, PlanIssue
from orion.planner import PlanOptions
from tests_support import make_plan
from test_api import client

@pytest.mark.parametrize('directory',[False,True])
def test_clear_reconfirm_organised_keeps_transfer_state(library,tmp_path,context,directory):
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=directory)
    executor=Executor(library,planner);forward=executor.execute(plan.id,1,context)
    iid=plan.operations[0].item_id;before=library.get(iid)
    cleared=library.clear_decision(iid)
    assert cleared.status=='organised' and cleared.decision is None
    assert cleared.path==before.path and cleared.signature==before.signature
    corrected=library.decide(iid,MatchDecision(item_id=iid,metadata={'title':'Corrected','year':'2024'}))
    assert corrected.status=='organised'
    assert target.read_bytes()==b'original media bytes' and not source.exists()
    undo=executor.undo_plan(forward.batch_id);assert not undo.issues
    assert executor.execute(undo.id,1,context).state=='completed'
    assert source.read_bytes()==b'original media bytes' and library.get(iid).status=='approved'


def add_destination(client,root):
    root.mkdir()
    response=client.post('/api/v1/destinations',json={'path':str(root)})
    assert response.status_code==201
    return response.json()['id']


def history(client,root,mentioned=None,source_root=None,roots=True):
    runtime=client.app.state.services;pid=str(uuid4())
    op=Operation(id=str(uuid4()),plan_id=pid,item_id='fixture',source=str((source_root or root.parent/'incoming')/'movie.mkv'),destination=str(root/'Movie.mkv'),expected_signature={},verification={'source_root':str(source_root or root.parent/'incoming'),'destination_root':str(root)} if roots else {})
    plan=OperationPlan(id=pid,operations=[op],warnings=[PlanIssue(code='fixture',detail=mentioned or '')])
    runtime.planner.save(plan)

@pytest.mark.parametrize('name,other',[('lib','library'),('lib_1','libX1'),('lib%1','library1')])
def test_remove_destination_ignores_substrings_and_sql_wildcards(client,tmp_path,name,other):
    did=add_destination(client,tmp_path/name)
    history(client,tmp_path/other)
    response=client.delete('/api/v1/destinations/'+did)
    assert response.status_code==200, response.text


def test_remove_destination_ignores_path_in_warning_text(client,tmp_path):
    root=tmp_path/'unreferenced';did=add_destination(client,root)
    history(client,tmp_path/'actual',mentioned=str(root))
    assert client.delete('/api/v1/destinations/'+did).status_code==200

@pytest.mark.parametrize('source,roots',[ (False,True),(True,True),(False,False)])
def test_remove_destination_preserves_real_operation_reference(client,tmp_path,source,roots):
    root=tmp_path/'referenced';did=add_destination(client,root)
    history(client,tmp_path/'other' if source else root,source_root=root if source else None,roots=roots)
    response=client.delete('/api/v1/destinations/'+did)
    assert response.status_code==400 and 'recovery history' in response.text
    assert any(d['id']==did for d in client.get('/api/v1/destinations').json())
