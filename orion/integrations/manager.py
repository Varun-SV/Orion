"""Persistent server configuration with independently retryable jobs."""
import hashlib
import json
from contextlib import nullcontext
from pydantic import Field
from orion.models import Record
from orion.library import Library
from orion.store import safe_metadata,utcnow
from orion.integrations.server import MediaServerClient,ServerQuery,ServerError,server_url
from orion.gaps import TmdbCatalogue,EpisodeGaps,ProviderMapping
from orion.providers import ProviderError

def _signature_fingerprint(signature):
    return hashlib.sha256(json.dumps(signature,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()

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

    def mapping_revision(self):
        """Stable persisted identity of the server and selected user, not credentials."""
        config=self.configuration()
        return hashlib.sha256(json.dumps([config.url,config.server_type,config.user_id,config.enabled]).encode()).hexdigest()

    def revision(self):
        # Keep a process-local generation for in-flight authentication safety;
        # do not use it as a durable key for saved episode mappings.
        return hashlib.sha256(json.dumps([self.mapping_revision(),
            self.runtime.config.key_revision('media_server')]).encode()).hexdigest()

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
        with self.runtime.config._lock:
            self.runtime.config.set_pref('media_server_settings',config.model_dump())
            self.runtime.config.set_pref('server_health',{'health':'not_checked','detail':''})
            return self.status()

    def client(self,payload):
        # Settings and their revision are one snapshot. A concurrent save
        # must never pair an old queued job with a replacement server URL.
        with self.runtime.config._lock:
            if payload.get('server_revision')!=self.revision():raise ServerError('server_configuration_changed')
            config=self.configuration()
            if not config.enabled or not config.url:raise ServerError('server_not_configured')
            key=self.runtime.config.get_api_key('media_server')
            return MediaServerClient(config.url,key,config.server_type,config.user_id)

    def submit(self,kind,payload=None):
        with self.runtime.config._lock:
            # The durable identity survives a process restart but changes when
            # the selected server/user changes. The revision also pins secrets.
            snapshot = {**(payload or {}),'server_revision':self.revision(),
                        'server_identity':self.mapping_revision()}
        return self.runtime.jobs.submit(kind,snapshot)

    @staticmethod
    def _publication_guard(context):
        # Cancellation takes this guard when setting the job event. Thus a
        # cancelled job cannot publish after the cancel request linearizes.
        event = getattr(context,'event',None)
        return getattr(event,'publication_lock',None) or nullcontext()

    def _publish_hints(self,item,revision,rows,state='ready',error=None,context=None):
        updates=safe_metadata({'server_hints':rows,'server_hint_state':state,'server_hint_error':error,
            'server_hint_revision':revision,'server_hint_signature':_signature_fingerprint(item.signature),
            'server_hint_decision':item.decision.model_dump() if item.decision else None})
        # Keep configuration stable while checking the current item and merging
        # hints in the same writer transaction; other annotations remain intact.
        with self.runtime.config._lock,self._publication_guard(context),self.runtime.store.transaction() as conn:
            if context is not None and context.cancelled():return 'server_hints_cancelled'
            if revision!=self.revision():return 'server_configuration_changed'
            row=conn.execute('SELECT * FROM orion_items WHERE id=?',(item.id,)).fetchone()
            if row is None:return 'item_changed'
            latest=Library.from_row(row)
            if latest.signature!=item.signature or latest.decision!=item.decision:return 'item_changed'
            metadata={**latest.metadata,**updates}
            conn.execute('UPDATE orion_items SET metadata=?,updated_at=? WHERE id=?',
                (json.dumps(metadata),utcnow(),item.id))
        return None

    def saved_hints(self,item_id):
        with self.runtime.config._lock:
            item=self.runtime.library.get(item_id)
            metadata=item.metadata
            decision=item.decision.model_dump() if item.decision else None
            if (metadata.get('server_hint_revision')!=self.revision()
                or metadata.get('server_hint_signature')!=_signature_fingerprint(item.signature)
                or 'server_hint_decision' not in metadata
                or metadata['server_hint_decision']!=decision):
                return {'items':[],'state':'not_checked','error':None}
            return {'items':metadata.get('server_hints',[]),'state':metadata.get('server_hint_state','not_checked'),
                    'error':metadata.get('server_hint_error')}

    def run(self,kind,payload,context):
        client=self.client(payload)
        try:
            if kind=='server_test':
                info=client.test_connection(context)
                users=client.users(context)
                with self.runtime.config._lock,self._publication_guard(context):
                    if payload['server_revision'] != self.revision():
                        raise ServerError('server_configuration_changed')
                    if context.cancelled():
                        raise ServerError('server_test_cancelled')
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
                hints=client.items(ServerQuery(search=str(metadata.get('title',''))[:200],include_types=media_type,max_items=30),context)[:30]
                rows=[]
                for hint in hints:
                    evidence=['Server search result; content has not been hashed']
                    if item.decision and hint.provider_ids.get(item.decision.provider)==item.decision.provider_id and item.decision.provider_id:
                        evidence.append('Confirmed provider identifier agrees')
                    elif hint.name.casefold()==str(metadata.get('title','')).casefold():evidence.append('Title agrees; identity needs review')
                    rows.append({**hint.model_dump(),'evidence':evidence})
                if context.cancelled():raise ServerError('server_hints_cancelled')
                changed=self._publish_hints(item,payload['server_revision'],rows,context=context)
                if changed:raise ServerError(changed)
                return {'item_id':item.id,'items':rows,'complete':True}
            if kind=='episode_gaps':
                mapping=ProviderMapping.model_validate(payload['mapping'])
                report=EpisodeGaps(client,self.catalogue).compare(payload['series_id'],mapping,payload.get('include_specials',False),context)
                # Publish only while the submitted server identity is still current.
                with self.runtime.config._lock,self._publication_guard(context):
                    if payload['server_revision']!=self.revision():raise ServerError('server_configuration_changed')
                    if context.cancelled():raise ServerError('server_gaps_cancelled')
                    if report.state=='ready':
                        with self.runtime.store.transaction() as conn:
                            if context.cancelled():raise ServerError('server_gaps_cancelled')
                            conn.execute('INSERT OR REPLACE INTO orion_settings VALUES(?,?)',('server_mapping_'+self.mapping_revision()+'_'+payload['series_id'],mapping.model_dump_json()))
                return report
            raise ValueError('Unknown server job')
        except ProviderError as exc:
            with self.runtime.config._lock:
                if payload['server_revision']==self.revision() and not context.cancelled() and exc.code not in ('item_changed','server_configuration_changed','server_test_cancelled','server_hints_cancelled','server_gaps_cancelled'):
                    self.runtime.config.set_pref('server_health',{'health':'unavailable','detail':exc.code})
            if kind=='server_hints' and not context.cancelled() and exc.code not in ('item_changed','server_configuration_changed','server_hints_cancelled'):
                if context.cancelled():raise ServerError('server_hints_cancelled') from exc
                changed=self._publish_hints(item,payload['server_revision'],[],'unavailable',exc.code,context=context)
                if changed=='server_hints_cancelled':
                    raise ServerError(changed) from exc
                # An item/configuration changed while the request was in
                # flight: don't publish its hints, but retain the *original*
                # provider exception for the caller and job history.
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
