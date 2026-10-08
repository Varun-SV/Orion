from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Response
from pydantic import Field
from orion.models import Record
from orion.naming import NamingProfile
from orion.profiles import Profiles
from orion.reports import Reports
from orion.routes.common import services
from orion.services import Services

router=APIRouter(prefix='/api/v1')
Runtime=Annotated[Services,Depends(services)]

class WatchUpdate(Record):
    enabled: bool
    identify_arrivals: bool = False
    stability_seconds: int = Field(default=30,ge=5,le=3600)

class CompareRequest(Record):
    item_ids: list[str] = Field(min_length=2,max_length=500)
    exact: bool = False

@router.get('/profiles')
def profiles(runtime:Runtime):
    return Profiles(runtime.library).list()

@router.put('/profiles/{profile_id}')
def save_profile(profile_id:str,body:NamingProfile,runtime:Runtime):
    if profile_id != body.id:
        raise ValueError('Profile ID must match the requested path')
    return Profiles(runtime.library).save(body)

@router.post('/profiles/preview')
def profile_preview(body:NamingProfile,runtime:Runtime):
    return {'examples':Profiles.examples(body),'fictional':True}

@router.get('/sources/{source_id}/watch')
def watch(source_id:str,runtime:Runtime):
    return runtime.watcher.settings(source_id)

@router.put('/sources/{source_id}/watch')
def update_watch(source_id:str,body:WatchUpdate,runtime:Runtime):
    return runtime.watcher.configure(source_id,**body.model_dump())

@router.post('/comparisons',status_code=202)
def compare(body:CompareRequest,runtime:Runtime):
    if len(set(body.item_ids)) < 2:
        raise ValueError('Select at least two different items')
    for item_id in body.item_ids:
        runtime.library.get(item_id)
    return runtime.jobs.submit('comparison',body.model_dump())

@router.get('/jobs/{job_id}/report')
def report(job_id:str,runtime:Runtime,format:Literal['csv','json']='csv'):
    content=Reports(runtime.store).export(job_id,format)
    # UUIDs are generated internally, but historic IDs may be arbitrary.
    safe_id=''.join(c for c in job_id if c.isalnum() or c in '-_')[:80] or 'job'
    return Response(content,media_type='text/csv' if format=='csv' else 'application/json',
        headers={'Content-Disposition':f'attachment; filename="orion-{safe_id}.{format}"'})
