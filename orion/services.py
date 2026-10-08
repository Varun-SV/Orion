from dataclasses import dataclass
from orion.config import Config
from orion.store import Store
from orion.library import Library
from orion.discovery import Discovery
from orion.providers import Providers,ProviderError
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

    def lookup(self,payload,context):
        item = self.library.get(payload['item_id'])
        try:
            candidates = self.providers.candidates(item,context,provider=payload.get('provider'))
            if self.library.get(item.id).signature != item.signature:
                raise ProviderError('item_changed',payload.get('provider') or 'lookup')
            self.library.annotate(item.id,candidates=[r.model_dump() for r in candidates],lookup_state='ready' if candidates else 'no_match',lookup_error=None)
            if not candidates and not self.library.get(item.id).decision:
                self.library.status(item.id,'no_match')
            return {'item_id':item.id,'candidates':[r.model_dump() for r in candidates]}
        except ProviderError as exc:
            self.library.annotate(item.id,lookup_state='error',lookup_error=exc.code)
            self.library.status(item.id,'error')
            raise

    def handlers(self):
        return {'recovery':lambda p,c:self.executor.reconcile(context=c),
                'scan':lambda p,c:self.discovery.scan(p['source_ids'],p.get('deep',False),c),
                'lookup':self.lookup,
                'organise':lambda p,c:self.executor.execute(p['plan_id'],p['revision'],c),
                'undo':lambda p,c:self.executor.execute(p['plan_id'],p['revision'],c),
                'provider_test':self.test_provider}

    def test_provider(self,payload,context):
        try:
            return self._test_provider(payload,context)
        except ProviderError as exc:
            self.config.set_pref('provider_health_'+payload['provider'],{'health':'unavailable','detail':exc.code})
            raise

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
        self.config.set_pref('provider_health_'+provider,result)
        return {'provider':provider,**result}
