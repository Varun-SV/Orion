from typing import Annotated,Literal
from fastapi import APIRouter,Depends
from pydantic import Field,SecretStr
from orion.models import Record
from orion.gaps import ProviderMapping
from orion.integrations.manager import ServerSettings
from orion.routes.common import services
from orion.services import Services

router=APIRouter(prefix='/api/v1')
Runtime=Annotated[Services,Depends(services)]
class Credentials(Record):
    key:SecretStr=Field(max_length=1000)
    session_only:bool=False
class DiscoveryRequest(Record):
    include_types:Literal['Movie,Series,Audio,MusicAlbum,Book','Movie','Series','Audio','Book']='Movie,Series,Audio,MusicAlbum,Book'
    search:str=Field(default='',max_length=200)
class GapRequest(Record):
    series_id:str=Field(min_length=1,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    mapping:ProviderMapping
    include_specials:bool=False

@router.get('/server')
def status(runtime:Runtime):return runtime.server.status()
@router.put('/server')
def configure(body:ServerSettings,runtime:Runtime):return runtime.server.save(body)
@router.post('/server/credentials')
def credentials(body:Credentials,runtime:Runtime):
    result=runtime.config.set_api_key('media_server',body.key.get_secret_value(),body.session_only)
    runtime.config.set_pref('server_health',{'health':'not_checked','detail':''})
    return result
@router.delete('/server/credentials')
def clear(runtime:Runtime):
    runtime.config.set_api_key('media_server','')
    runtime.config.set_pref('server_health',{'health':'not_checked','detail':''})
    return {'configured':False}
@router.post('/server/test',status_code=202)
def test(runtime:Runtime):return runtime.server.submit('server_test')
@router.post('/server/discover',status_code=202)
def discover(body:DiscoveryRequest,runtime:Runtime):return runtime.server.submit('server_discover',{'query':body.model_dump()})
@router.post('/server/refresh',status_code=202)
def refresh(runtime:Runtime):return runtime.server.submit('server_refresh')
@router.post('/server/gaps',status_code=202)
def gaps(body:GapRequest,runtime:Runtime):return runtime.server.submit('episode_gaps',body.model_dump())
@router.post('/items/{item_id}/server-hints',status_code=202)
def hints(item_id:str,runtime:Runtime):
    runtime.library.get(item_id)
    return runtime.server.submit('server_hints',{'item_id':item_id})
@router.get('/items/{item_id}/server-hints')
def saved_hints(item_id:str,runtime:Runtime):
    metadata=runtime.library.get(item_id).metadata
    if metadata.get('server_hint_revision')!=runtime.server.revision():return {'items':[],'state':'not_checked','error':None}
    return {'items':metadata.get('server_hints',[]),'state':metadata.get('server_hint_state','not_checked'),'error':metadata.get('server_hint_error')}

@router.get('/server/mapping/{series_id}')
def saved_mapping(series_id:str,runtime:Runtime):
    with runtime.store.transaction() as conn:
        row=conn.execute('SELECT value FROM orion_settings WHERE key=?',('server_mapping_'+runtime.server.revision()+'_'+series_id,)).fetchone()
    return ProviderMapping.model_validate_json(row[0]) if row else None
