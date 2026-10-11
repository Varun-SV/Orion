from dataclasses import dataclass
import requests
from orion.config import Config
from orion.store import Store
from orion.library import Library
from orion.discovery import Discovery,Cancelled
from orion.providers import Providers,ProviderError,transport_error
from orion.planner import Planner
from orion.executor import Executor

@dataclass
class Services:
    config: Config
    store: Store
    library: Library
    discovery: Discovery
    providers: Providers
    planner: Planner
    executor: Executor
    jobs: object = None
    watcher: object = None
    server: object = None

    def lookup(self,payload,context):
        item = self.library.get(payload['item_id'])
        generation = payload.get('lookup_generation')
        try:
            if payload.get('signature') and (item.signature != payload['signature'] or item.decision):
                return {'item_id':item.id,'skipped':True,'reason':'item_changed'}
            if 'lookup_generation' not in payload:
                generation = self.library.begin_lookup(item.id,item.signature)
            if generation is None or self.library.get(item.id).metadata.get('_lookup_generation') != generation:
                return {'item_id':item.id,'skipped':True,'reason':'lookup_superseded'}
            candidates = self.providers.candidates(item,context,provider=payload.get('provider'))
            values=[r.model_dump() for r in candidates]
            if context.cancelled():raise Cancelled()
            if not self.library.publish_lookup(item.id,item.signature,values,item.decision,generation=generation):
                # A changed file is a failed lookup; a concurrently confirmed
                # decision simply supersedes a stale result without an error.
                current = self.library.get(item.id)
                if current.signature != item.signature:
                    raise ProviderError('item_changed',payload.get('provider') or 'lookup')
                return {'item_id':item.id,'candidates':[],'skipped':True,
                        'reason':'lookup_superseded' if current.metadata.get('_lookup_generation') != generation else 'item_changed'}
            return {'item_id':item.id,'candidates':values}
        except ProviderError as exc:
            if context.cancelled():raise Cancelled() from None
            self.library.lookup_failed(item.id,item.signature,exc.code,item.decision,generation=generation)
            raise

    def handlers(self):
        return {'recovery':lambda p,c:self.executor.reconcile(context=c),
                'scan':lambda p,c:self.discovery.scan(p['source_ids'],p.get('deep',False),c),
                'lookup':self.lookup,
                'organise':self.organise,
                'undo':self.organise,
                'provider_test':self.test_provider,
                'comparison':self.compare,
                'watch_scan':lambda p,c:self.watcher.scan_ready(p,c),
                **{kind:(lambda p,c,kind=kind:self.server.run(kind,p,c)) for kind in ('server_test','server_discover','server_refresh','server_hints','episode_gaps')}}

    def organise(self,payload,context):
        result = self.executor.execute(payload['plan_id'],payload['revision'],context)
        return self.server.after_local_success(result)

    def compare(self,payload,context):
        from orion.duplicates import Duplicates
        return Duplicates(self.library).compare(payload['item_ids'],payload.get('exact',False),context)

    def test_provider(self,payload,context):
        provider = payload['provider']
        # API submissions pin a revision at queue time; direct/legacy calls
        # pin it at execution time to preserve supported job retries.
        revision = payload.get('provider_revision',self.config.key_revision(provider))
        with self.config._lock:
            if revision != self.config.key_revision(provider):
                raise ProviderError('provider_configuration_changed',provider)
        try:
            result = self._test_provider(payload,context)
        except (ProviderError,requests.RequestException) as exc:
            error = exc if isinstance(exc,ProviderError) else transport_error(exc,provider)
            with self.config._lock:
                if context.cancelled():
                    raise Cancelled() from None
                if revision != self.config.key_revision(provider):
                    raise ProviderError('provider_configuration_changed',provider) from None
                self.config.set_pref('provider_health_'+provider,{'health':'unavailable','detail':error.code})
            raise error from None
        with self.config._lock:
            if context.cancelled():
                raise Cancelled()
            if revision != self.config.key_revision(provider):
                raise ProviderError('provider_configuration_changed',provider)
            self.config.set_pref('provider_health_'+provider,result)
        return {'provider':provider,**result}

    def _test_provider(self,payload,context):
        provider = payload['provider']
        if provider in ('audd','acoustid'):
            result = {'health':'requires_sample','detail':'Test by identifying a selected music item after enabling consent.'}
        elif provider=='tmdb':
            self.providers._call(provider,'GET','https://api.themoviedb.org/3/configuration',context,params={'api_key':self.providers._key(provider)})
            result = {'health':'connected','detail':'Configuration request succeeded.'}
        elif provider=='musicbrainz':
            self.providers._call(provider,'GET','https://musicbrainz.org/ws/2/recording',context,params={'query':'recording:Arrival','limit':1,'fmt':'json'})
            result = {'health':'connected','detail':'Catalogue request succeeded.'}
        elif provider=='openlibrary':
            self.providers._call(provider,'GET','https://openlibrary.org/search.json',context,params={'q':'Arrival','limit':1,'fields':'key'})
            result = {'health':'connected','detail':'Catalogue request succeeded.'}
        elif provider=='anilist':
            body = self.providers._call(provider,'POST','https://graphql.anilist.co',context,json={'query':'query { Page(perPage:1) { media(type:ANIME) { id } } }'})
            if body.get('errors'): raise ProviderError('provider_unavailable',provider)
            result = {'health':'connected','detail':'Catalogue request succeeded.'}
        else:
            from orion.anidb_titles import search_titles
            search_titles('Example',self.config,context)
            result = {'health':'cached','detail':'Title catalogue available; this is not an authenticated server check.'}
        return result
