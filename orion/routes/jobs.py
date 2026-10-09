from typing import Annotated,Literal
from fastapi import APIRouter,Depends,Query
from pydantic import Field
from orion.models import Record
from orion.routes.common import services
from orion.services import Services

router = APIRouter(prefix='/api/v1')
Runtime = Annotated[Services,Depends(services)]

class ScanPayload(Record):
    source_ids: list[str] = Field(max_length=100)
    deep: bool = False

class JobCreate(Record):
    kind: Literal['scan']
    payload: ScanPayload

class LookupRequest(Record):
    provider: Literal['tmdb','anilist','anidb','musicbrainz','acoustid','audd','openlibrary'] | None = None

@router.get('/jobs')
def jobs(runtime:Runtime,limit:int=Query(100,ge=1,le=500)):
    return runtime.jobs.list(limit)

@router.post('/jobs',status_code=202)
def submit(body:JobCreate,runtime:Runtime):
    payload = body.payload
    from orion.routes.settings import sources
    known = {s['id']:s for s in sources(runtime)}
    if any(sid not in known or known[sid]['archived'] for sid in payload.source_ids):
        raise ValueError('Select active configured sources')
    return runtime.jobs.submit(body.kind,payload.model_dump())

@router.get('/jobs/{job_id}')
def get(job_id:str,runtime:Runtime):
    return runtime.jobs.get(job_id)

@router.post('/jobs/{job_id}/cancel')
def cancel(job_id:str,runtime:Runtime):
    return runtime.jobs.cancel(job_id)

@router.post('/jobs/{job_id}/retry')
def retry(job_id:str,runtime:Runtime):
    return runtime.jobs.retry(job_id)

@router.post('/items/{item_id}/candidates',status_code=202)
def identify(item_id:str,body:LookupRequest,runtime:Runtime):
    runtime.library.get(item_id)
    return runtime.jobs.submit('lookup',{'item_id':item_id,'provider':body.provider})
