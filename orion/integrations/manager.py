"""Persistent server configuration with independently retryable jobs."""
import hashlib
import json
from pydantic import Field
from orion.models import Record
from orion.integrations.server import MediaServerClient,ServerQuery,ServerError,server_url
from orion.gaps import TmdbCatalogue,EpisodeGaps,ProviderMapping
from orion.providers import ProviderError

class ServerSettings(Record):
    enabled:bool=False
    url:str=Field(default='',max_length=2048)
    server_type:str='jellyfin'
    user_id:str=Field(default='',max_length=100,pattern=r'^[A-Za-z0-9_-]*$')
    auto_refresh:bool=False

class ServerIntegration:
    def __init__(self,runtime):
        self.runtime=runtime
        self.catalogue=TmdbCatalogue(runtime.store,runtime.providers)

    def configuration(self):
        return ServerSettings.model_validate(self.runtime.config.get_pref('media_server_settings',{}))

    def revision(self):
        config=self.configuration()
        return hashlib.sha256(json.dumps([config.url,config.server_type,config.user_id,config.enabled]).encode()).hexdigest()

    def status(self):
        config=self.configuration()
        key=self.runtime.config.get_api_key('media_server')
        return {**config.model_dump(),'configured':bool(config.enabled and config.url and key),
                'storage':'session' if 'media_server' in self.runtime.config._session_services else 'keychain',
                **self.runtime.config.get_pref('server_health',{'health':'not_checked','detail':''})}

    def save(self,config):
        if config.server_type not in ('jellyfin','emby'):raise ValueError('Choose Jellyfin or Emby')
        if config.enabled and not config.url:raise ValueError('Enter the server URL before enabling integration')
        if config.url:config=config.model_copy(update={'url':server_url(config.url)})
        self.runtime.config.set_pref('media_server_settings',config.model_dump())
        self.runtime.config.set_pref('server_health',{'health':'not_checked','detail':''})
        return self.status()

    def client(self,payload):
        if payload.get('server_revision')!=self.revision():raise ServerError('server_configuration_changed')
        config=self.configuration()
        if not config.enabled or not config.url:raise ServerError('server_not_configured')
        return MediaServerClient(config.url,self.runtime.config.get_api_key('media_server'),config.server_type,config.user_id)

    def submit(self,kind,payload=None):
        return self.runtime.jobs.submit(kind,{**(payload or {}),'server_revision':self.revision()})

    def run(self,kind,payload,context):
        client=self.client(payload)
        try:
            if kind=='server_test':
                info=client.test_connection(context)
                users=client.users(context)
                self.runtime.config.set_pref('server_health',{'health':'connected','detail':info.name+' · '+info.version})
                return {'server':info.model_dump(),'users':[u.model_dump() for u in users]}
            if kind=='server_discover':
                items=client.items(ServerQuery.model_validate(payload['query']),context)
                return {'items':[i.model_dump() for i in items],'user_id':client.user_id,'complete':True}
            if kind=='server_refresh':return client.refresh(context)
            if kind=='server_hints':
                item=self.runtime.library.get(payload['item_id'])
                metadata={**item.metadata,**(item.decision.metadata if item.decision else {})}
                media_type='Audio' if item.kind=='music' else 'Book' if item.kind=='books' else 'Series' if item.kind in ('series','anime','web_series') else 'Movie'
                hints=client.items(ServerQuery(search=str(metadata.get('title',''))[:200],include_types=media_type),context)
                rows=[]
                for hint in hints:
                    evidence=['Server search result; content has not been hashed']
                    if item.decision and hint.provider_ids.get(item.decision.provider)==item.decision.provider_id and item.decision.provider_id:
                        evidence.append('Confirmed provider identifier agrees')
                    elif hint.name.casefold()==str(metadata.get('title','')).casefold():evidence.append('Title agrees; identity needs review')
                    rows.append({**hint.model_dump(),'evidence':evidence})
                self.runtime.library.annotate(item.id,server_hints=rows,server_hint_state='ready',server_hint_error=None,server_hint_revision=payload['server_revision'])
                return {'item_id':item.id,'items':rows,'complete':True}
            if kind=='episode_gaps':
                mapping=ProviderMapping.model_validate(payload['mapping'])
                report=EpisodeGaps(client,self.catalogue).compare(payload['series_id'],mapping,payload.get('include_specials',False),context)
                if report.state=='ready':
                    with self.runtime.store.transaction() as conn:
                        conn.execute('INSERT OR REPLACE INTO orion_settings VALUES(?,?)',('server_mapping_'+self.revision()+'_'+payload['series_id'],mapping.model_dump_json()))
                return report
            raise ValueError('Unknown server job')
        except ProviderError as exc:
            self.runtime.config.set_pref('server_health',{'health':'unavailable','detail':exc.code})
            if kind=='server_hints':self.runtime.library.annotate(payload['item_id'],server_hint_state='unavailable',server_hint_error=exc.code,server_hints=[],server_hint_revision=payload['server_revision'])
            raise

    def after_local_success(self,result):
        config=self.configuration()
        document=result.model_dump()
        if result.state!='completed' or not result.completed_operation_ids or not config.auto_refresh or not self.status()['configured']:
            return document
        key='refresh_batch_'+result.batch_id
        with self.runtime.store.transaction() as conn:
            previous=conn.execute('SELECT value FROM orion_settings WHERE key=?',(key,)).fetchone()
        if previous:
            document['refresh_job_id']=previous[0]
            return document
        try:
            job=self.submit('server_refresh',{'batch_id':result.batch_id})
            with self.runtime.store.transaction() as conn:conn.execute('INSERT OR REPLACE INTO orion_settings VALUES(?,?)',(key,job.id))
            document['refresh_job_id']=job.id
        except (ValueError,RuntimeError):
            document['refresh_error']='refresh_queue_unavailable'
        return document
