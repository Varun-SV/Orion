from typing import Annotated,Literal
from fastapi import APIRouter,Depends
from pydantic import Field
from orion.models import Record, OperationPlan
from orion.planner import PlanOptions
from orion.routes.common import services
from orion.services import Services

router = APIRouter(prefix='/api/v1')
Runtime = Annotated[Services,Depends(services)]

class PlanCreate(Record):
    item_ids: list[str] = Field(min_length=1,max_length=500)
    options: PlanOptions = Field(default_factory=PlanOptions)

class UndoSelection(Record):
    exclude_operation_ids: list[str] = Field(default_factory=list,max_length=5000)

class PlanRef(Record):
    revision: int = Field(ge=1)

@router.get('/plans')
def plans(runtime:Runtime):
    with runtime.store.transaction() as conn:
        return [OperationPlan.model_validate_json(r['data']) for r in conn.execute('SELECT data FROM orion_plans ORDER BY created_at DESC LIMIT 100')]

@router.post('/plans',status_code=201)
def create(body:PlanCreate,runtime:Runtime):
    return runtime.planner.create(body.item_ids,body.options)

@router.get('/plans/{plan_id}')
def get(plan_id:str,runtime:Runtime):
    return runtime.planner.get(plan_id)

@router.post('/plans/{plan_id}/revalidate')
def validate(plan_id:str,body:PlanRef,runtime:Runtime):
    return runtime.planner.validate(plan_id,body.revision)

@router.post('/plans/{plan_id}/execute',status_code=202)
def execute(plan_id:str,body:PlanRef,runtime:Runtime):
    plan = runtime.planner.validate(plan_id,body.revision)
    if plan.issues: raise ValueError('Resolve preflight issues before executing')
    if not plan.operations: raise ValueError('This plan has no changes')
    kind = 'undo' if any(op.verification.get('undo_of') for op in plan.operations) else 'organise'
    return runtime.jobs.submit(kind,{'plan_id':plan_id,'revision':body.revision})

@router.get('/plans/{plan_id}/operations')
def operations(plan_id:str,runtime:Runtime):
    runtime.planner.get(plan_id)
    return runtime.executor.operations(plan_id)

@router.get('/batches')
def batches(runtime:Runtime):
    import json
    with runtime.store.transaction() as conn:
        return [{**dict(r),'data':json.loads(r['data'])} for r in conn.execute('SELECT * FROM orion_batches ORDER BY created_at DESC LIMIT 100')]

@router.post('/batches/{batch_id}/undo-plan',status_code=201)
def undo(batch_id:str,runtime:Runtime,body:UndoSelection | None = None):
    return runtime.executor.undo_plan(batch_id,body.exclude_operation_ids if body else [])
