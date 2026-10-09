from pathlib import Path
from typing import Annotated,Literal
from fastapi import APIRouter,Depends
from pydantic import Field,SecretStr
from orion.models import Record,Kind
from orion.store import item_id,normalized,is_secret
from orion.providers import PROVIDERS,compatible_providers,ProviderError,validate_provider
from orion.discovery import linked
from orion.naming import valid_relative
from orion.routes.common import services
from orion.services import Services

router = APIRouter(prefix='/api/v1')
Runtime = Annotated[Services,Depends(services)]
ProviderName = Literal['tmdb','anilist','anidb','musicbrainz','acoustid','audd','openlibrary']

class SourceCreate(Record):
    path: str = Field(min_length=1,max_length=4096)
    label: str = Field(default='',max_length=100)
    kind: Literal['auto','movies','series','anime','anime_films','web_series','music','books'] = 'auto'

class DestinationCreate(Record):
    path: str = Field(min_length=1,max_length=4096)
    label: str = Field(default='Library',max_length=100)

class SettingsUpdate(Record):
    theme: Literal['ivory','clay','night'] | None = None
    view: Literal['grid','list'] | None = None
    fingerprint_enabled: bool | None = None
    audd_enabled: bool | None = None
    default_destination: str | None = None
    providers: dict[Kind,ProviderName] | None = None

class CredentialUpdate(Record):
    key: SecretStr
    session_only: bool = False

class CategoryUpdate(Record):
    dest_subpath: str = Field(min_length=1,max_length=300)
    api_pref: ProviderName

@router.get('/sources')
def sources(runtime:Runtime):
    with runtime.store.transaction() as conn:
        archived = {r['key'].removeprefix('source_archived_') for r in conn.execute("SELECT key FROM orion_settings WHERE key LIKE 'source_archived_%' AND value='true'")}
    return [{**r,'archived':r['id'] in archived} for r in runtime.library.sources()]

@router.post('/sources',status_code=201)
def add_source(body:SourceCreate,runtime:Runtime):
    root = Path(body.path).absolute()
    with runtime.store.transaction() as conn:
        destinations = [Path(r[0]) for r in conn.execute('SELECT path FROM orion_destinations')]
    if any(root.is_relative_to(d) or d.is_relative_to(root) for d in destinations):
        raise ValueError('Source and destination roots cannot overlap')
    return runtime.library.add_source(root,body.label,body.kind)

@router.delete('/sources/{source_id}')
def archive_source(source_id:str,runtime:Runtime):
    if not any(r['id']==source_id for r in runtime.library.sources()): raise KeyError('Source not found')
    with runtime.store.transaction() as conn:
        conn.execute('INSERT OR REPLACE INTO orion_settings VALUES(?,?)',('source_archived_'+source_id,'true'))
        conn.execute('UPDATE orion_sources SET watch=0 WHERE id=?',(source_id,))
    return {'id':source_id,'archived':True,'detail':'Scan source paused; indexed items and recovery history are preserved.'}

@router.post('/sources/{source_id}/resume')
def resume_source(source_id:str,runtime:Runtime):
    source = next((s for s in runtime.library.sources() if s['id']==source_id),None)
    if not source: raise KeyError('Source not found')
    root = Path(source['path'])
    if not root.is_dir() or linked(root): raise ValueError('Reconnect the source folder before resuming')
    with runtime.store.transaction() as conn:
        conn.execute('DELETE FROM orion_settings WHERE key=?',('source_archived_'+source_id,))
    return {'id':source_id,'archived':False}
@router.get('/destinations')
def destinations(runtime:Runtime):
    with runtime.store.transaction() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM orion_destinations ORDER BY label')]

@router.post('/destinations',status_code=201)
def add_destination(body:DestinationCreate,runtime:Runtime):
    root = Path(body.path).absolute()
    if not root.is_dir() or linked(root): raise ValueError('Choose an accessible destination folder, not a link')
    if any(root.is_relative_to(Path(s['path'])) or Path(s['path']).is_relative_to(root) for s in runtime.library.sources()):
        raise ValueError('Source and destination roots cannot overlap')
    did = item_id('destination',root)
    with runtime.store.transaction() as conn:
        conn.execute('INSERT INTO orion_destinations VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET label=excluded.label',(did,str(root),body.label))
    return {'id':did,'path':str(root),'label':body.label}

@router.delete('/destinations/{destination_id}')
def remove_destination(destination_id:str,runtime:Runtime):
    with runtime.store.transaction() as conn:
        row = conn.execute('SELECT path FROM orion_destinations WHERE id=?',(destination_id,)).fetchone()
        if not row: raise KeyError('Destination not found')
        if conn.execute('SELECT 1 FROM orion_plans WHERE data LIKE ? LIMIT 1',('%'+str(row['path']).replace('\\','\\\\')+'%',)).fetchone():
            raise ValueError('Destination is referenced by recovery history; keep it configured for undo.')
        conn.execute('DELETE FROM orion_destinations WHERE id=?',(destination_id,))
    return {'removed':True}

@router.get('/categories')
def categories(runtime:Runtime):
    with runtime.store.transaction() as conn:
        rows=[dict(r) for r in conn.execute('SELECT * FROM orion_categories ORDER BY name')]
    return [{**r,'api_pref':runtime.providers.preferred_provider(r['kind']),'compatible_providers':compatible_providers(r['kind'])} for r in rows]

@router.put('/categories/{category_id}')
def update_category(category_id:str,body:CategoryUpdate,runtime:Runtime):
    valid_relative(body.dest_subpath)
    with runtime.store.transaction() as conn:
        category = conn.execute('SELECT kind FROM orion_categories WHERE id=?',(category_id,)).fetchone()
        if not category: raise KeyError('Category not found')
        check_provider_preference(category['kind'],body.api_pref)
        changed = conn.execute('UPDATE orion_categories SET dest_subpath=?,api_pref=? WHERE id=?',(body.dest_subpath,body.api_pref,category_id)).rowcount
    if not changed: raise KeyError('Category not found')
    runtime.config.set_pref('provider_'+category['kind'],body.api_pref)
    return {'id':category_id,**body.model_dump()}

@router.get('/settings')
def settings(runtime:Runtime):
    cfg = runtime.config
    return {'theme':cfg.get_pref('theme','ivory'),'view':cfg.get_pref('view','grid'),'fingerprint_enabled':cfg.get_pref('fingerprint_enabled',False),
            'audd_enabled':cfg.get_pref('audd_enabled',False),'default_destination':cfg.get_pref('default_destination'),
            'providers':{k:runtime.providers.preferred_provider(k) for k in __import__('orion.models',fromlist=['KINDS']).KINDS}}

def check_provider_preference(kind,provider):
    try:
        validate_provider(kind,provider)
    except ProviderError:
        raise ValueError('Choose a compatible provider for '+kind) from None

@router.put('/settings')
def update_settings(body:SettingsUpdate,runtime:Runtime):
    updates = body.model_dump(exclude_none=True)
    for kind,provider in updates.get('providers',{}).items():
        check_provider_preference(kind,provider)
    for key,value in updates.items():
        if key=='providers':
            for kind,provider in value.items(): runtime.config.set_pref('provider_'+kind,provider)
        else:
            runtime.config.set_pref(key,value)
    return settings(runtime)

@router.get('/providers')
def providers(runtime:Runtime):
    cfg = runtime.config
    result = []
    for name in PROVIDERS:
        requires_key = name in ('tmdb','acoustid','audd')
        status = cfg.get_pref('provider_health_'+name,{})
        result.append({'id':name,'label':{'tmdb':'TMDb','anilist':'AniList','anidb':'AniDB','musicbrainz':'MusicBrainz','acoustid':'AcoustID','audd':'AudD','openlibrary':'Open Library'}[name],
                       'requires_key':requires_key,'configured':bool(cfg.get_api_key(name)) if requires_key else True,
                       'storage':'session' if name in cfg._session_services else 'keychain' if requires_key else 'not_required',
                       'health':status.get('health','not_checked'),'detail':status.get('detail',''),
                       'consent_enabled':cfg.get_pref('audd_enabled',False) if name=='audd' else cfg.get_pref('fingerprint_enabled',False) if name=='acoustid' else True})
    return result

@router.post('/providers/{provider}/credentials')
def credentials(provider:ProviderName,body:CredentialUpdate,runtime:Runtime):
    if provider not in ('tmdb','acoustid','audd'): raise ValueError('Provider does not use an API key')
    result = runtime.config.set_api_key(provider,body.key.get_secret_value(),body.session_only)
    runtime.config.set_pref('provider_health_'+provider,{'health':'not_checked'})
    return result

@router.post('/providers/{provider}/test',status_code=202)
def test_provider(provider:ProviderName,runtime:Runtime):
    return runtime.jobs.submit('provider_test',{'provider':provider})
