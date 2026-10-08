from typing import Annotated
from fastapi import APIRouter,Depends,Query
from orion.models import MatchDecision
from orion.routes.common import services
from orion.services import Services

router = APIRouter(prefix='/api/v1')
Runtime = Annotated[Services,Depends(services)]

@router.get('/overview')
def overview(runtime:Runtime):
    from orion.models import KINDS
    import json
    counts = dict.fromkeys(KINDS,0)
    statuses = {}
    indexed_bytes = 0
    with runtime.store.transaction() as conn:
        for row in conn.execute('SELECT kind,status,signature FROM orion_items'):
            counts[row['kind']] += 1
            statuses[row['status']] = statuses.get(row['status'],0)+1
            sig = json.loads(row['signature'])
            indexed_bytes += sig.get('size',sum(child.get('size',0) for child in sig.get('children',{}).values()))
        destinations = conn.execute('SELECT COUNT(*) FROM orion_destinations').fetchone()[0]
        jobs = conn.execute("SELECT COUNT(*) FROM orion_jobs WHERE state IN ('queued','running','cancelling')").fetchone()[0]
    from orion.routes.settings import sources
    return {'counts':counts,'status_counts':statuses,'total':sum(counts.values()),'review':sum(statuses.get(s,0) for s in ('pending','error','no_match')),
            'indexed_bytes':indexed_bytes,'sources':sum(not s['archived'] for s in sources(runtime)),'destinations':destinations,'jobs_running':jobs}

@router.get('/items')
def items(runtime:Runtime,query:str='',kind:str|None=None,status:str|None=None,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=500)):
    return runtime.library.query(query,kind,status,offset,limit)

@router.get('/items/{item_id}')
def item(item_id:str,runtime:Runtime):
    return runtime.library.get(item_id)

@router.put('/items/{item_id}/decision')
def decision(item_id:str,body:MatchDecision,runtime:Runtime):
    return runtime.library.decide(item_id,body)

@router.delete('/items/{item_id}/decision')
def clear_decision(item_id:str,runtime:Runtime):
    return runtime.library.clear_decision(item_id)

@router.get('/items/{item_id}/candidates')
def candidates(item_id:str,runtime:Runtime):
    item = runtime.library.get(item_id)
    return {'items':item.metadata.get('candidates',[]),'state':item.metadata.get('lookup_state','not_checked'),'error':item.metadata.get('lookup_error')}

@router.get('/activity')
def activity(runtime:Runtime,limit:int=Query(100,ge=1,le=500)):
    with runtime.store.transaction() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM orion_activity ORDER BY id DESC LIMIT ?',(limit,))]
