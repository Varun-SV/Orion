from __future__ import annotations
import re
import threading
import time
from pathlib import Path
import requests
from orion.models import Candidate, MediaItem, JobContext
from orion.discovery import Cancelled
from orion.store import safe_metadata

class ProviderError(RuntimeError):
    def __init__(self, code, provider):
        self.code, self.provider = code, provider
        super().__init__(f'{provider}: {code.replace("_", " ")}')

class RateLimiter:
    def __init__(self, intervals=None):
        self.intervals = intervals or {'musicbrainz':1.05,'anidb':2.1,'acoustid':0.35,'openlibrary':1.05,'anilist':1.0,'tmdb':0.1,'audd':1.0}
        self.lock = threading.Lock()
        self.last = {}

    def acquire(self, provider, context):
        while True:
            if context.cancelled():
                raise Cancelled()
            with self.lock:
                now = time.monotonic()
                wait = self.intervals.get(provider,0.2) - (now-self.last.get(provider,0))
                if wait <= 0:
                    self.last[provider] = now
                    return
            time.sleep(min(wait,0.05))

LIMITER = RateLimiter()
PROVIDER_KINDS = {
    'tmdb': ('movies','series','anime','anime_films','web_series'),
    'anilist': ('anime','anime_films'), 'anidb': ('anime','anime_films'),
    'musicbrainz': ('music',), 'acoustid': ('music',), 'audd': ('music',),
    'openlibrary': ('books',),
}
PROVIDERS = tuple(PROVIDER_KINDS)

def compatible_providers(kind):
    return [provider for provider,kinds in PROVIDER_KINDS.items() if kind in kinds]

def validate_provider(kind,provider):
    if provider not in PROVIDER_KINDS:
        raise ProviderError('unknown_provider',str(provider))
    if kind not in PROVIDER_KINDS[provider]:
        raise ProviderError('provider_incompatible',provider)

class Providers:
    def __init__(self, config, request=None):
        self.config = config
        self.request = request or self._request

    @staticmethod
    def _request(provider, method, url, context, **kwargs):
        for attempt in range(3):
            LIMITER.acquire(provider,context)
            try:
                with requests.request(method,url,timeout=(3,10),headers={'User-Agent':'Orion/0.2 (https://github.com/Varun-SV/Orion)'},**kwargs) as response:
                    if response.status_code in (429,503) and attempt < 2:
                        delay = min(float(response.headers.get('Retry-After',1)),3)
                        end = time.monotonic() + max(delay,0)
                        while time.monotonic() < end:
                            if context.cancelled(): raise Cancelled()
                            time.sleep(min(0.05,end-time.monotonic()))
                        continue
                    response.raise_for_status()
                    return response.json()
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 2:
                    raise
        raise ProviderError('provider_unavailable',provider)

    def _call(self, provider, method, url, context, **kwargs):
        if context.cancelled():
            raise Cancelled()
        return self.request(provider,method,url,context,**kwargs)

    def _key(self,provider):
        key = self.config.get_api_key(provider)
        if not key:
            raise ProviderError('credentials_required',provider)
        return key

    @staticmethod
    def _candidate(provider, identifier, title, year, metadata, item):
        title, year = str(title or ''), str(year or '')
        evidence = []
        def normalized(value): return re.sub(r'[^\w]','',str(value).casefold())
        if normalized(title) == normalized(item.metadata.get('title','')):
            evidence.append('Title agrees with parsed metadata')
        else:
            evidence.append('Title differs from parsed metadata; review required')
        parsed_year = str(item.metadata.get('year',''))
        if year and parsed_year:
            evidence.append('Year agrees with parsed metadata' if year == parsed_year else 'Year differs from parsed metadata')
        if metadata.get('artist') and item.metadata.get('artist'):
            evidence.append('Artist agrees with embedded tags' if normalized(metadata['artist']) == normalized(item.metadata['artist']) else 'Artist differs from embedded tags')
        return Candidate(provider=provider,provider_id=str(identifier or ''),title=title,year=year,
                         metadata=safe_metadata({'title':title,'year':year,**metadata}),evidence=evidence)

    def candidates(self, item: MediaItem, context: JobContext, provider=None) -> list[Candidate]:
        provider = provider or self.config.get_pref('provider_' + item.kind) or ('musicbrainz' if item.kind=='music' else 'openlibrary' if item.kind=='books' else 'anilist' if item.kind in ('anime','anime_films') else 'tmdb')
        validate_provider(item.kind,provider)
        title = str(item.metadata.get('title',''))
        try:
            raw = getattr(self,'_' + provider)(item,title,context)
            return [self._candidate(provider,*row,item) for row in raw if row[1]][:12]
        except (ProviderError,Cancelled):
            raise
        except requests.HTTPError as exc:
            code = 'credentials_rejected' if exc.response is not None and exc.response.status_code in (401,403) else 'provider_unavailable'
            raise ProviderError(code,provider) from None
        except (requests.RequestException,OSError,ValueError,KeyError,TypeError):
            raise ProviderError('provider_unavailable',provider) from None

    def _tmdb(self,item,title,context):
        from api.tmdb import TMDB_BASE, POSTER_BASE
        endpoint = 'tv' if item.kind in ('series','anime','web_series') else 'movie'
        params = {'query':title,'api_key':self._key('tmdb'),'language':'en-US'}
        if item.metadata.get('year'):
            params['first_air_date_year' if endpoint=='tv' else 'year'] = item.metadata['year']
        body = self._call('tmdb','GET',TMDB_BASE+'/search/'+endpoint,context,params=params)
        return [(r.get('id'),r.get('title') or r.get('name'),(r.get('release_date') or r.get('first_air_date') or '')[:4],
                 {'plot':r.get('overview',''),'poster_url':POSTER_BASE+r['poster_path'] if r.get('poster_path') else '', 'media_type':endpoint,'vote_rating':r.get('vote_average')}) for r in body['results']]

    def _anilist(self,item,title,context):
        from api.anilist import ANILIST_URL, _SEARCH_QUERY
        body = self._call('anilist','POST',ANILIST_URL,context,json={'query':_SEARCH_QUERY,'variables':{'search':title}})
        if body.get('errors'):
            raise ProviderError('provider_unavailable','anilist')
        return [(r['id'],r['title'].get('english') or r['title'].get('romaji'),(r.get('startDate') or {}).get('year'),
                 {'romaji':r['title'].get('romaji'),'episodes':r.get('episodes'),'poster_url':(r.get('coverImage') or {}).get('medium'),'format':r.get('format')}) for r in body['data']['Page']['media']]

    def _musicbrainz(self,item,title,context):
        artist = str(item.metadata.get('artist','')).replace('"','\\"')
        query = 'recording:"' + title.replace('"','\\"') + '"'
        if artist:
            query += ' AND artistname:"' + artist + '"'
        body = self._call('musicbrainz','GET','https://musicbrainz.org/ws/2/recording',context,params={'query':query,'limit':10,'fmt':'json'})
        return [self._recording(r) for r in body['recordings']]

    @staticmethod
    def _recording(r):
        releases = r.get('releases') or []
        release = releases[0] if releases else {}
        media = release.get('media') or []
        track = media[0] if media else {}
        metadata = {'artist':', '.join(a.get('name',a.get('artist',{}).get('name','')) for a in r.get('artist-credit',[]) if isinstance(a,dict)),
                    'album':release.get('title',''),'release_mbid':release.get('id',''),'recording_mbid':r.get('id',''),
                    'track_number':str(track.get('track-offset',0)+1) if media else '', 'disc_number':str(track.get('position',''))}
        return r.get('id'),r.get('title'),release.get('date','')[:4],metadata

    def _openlibrary(self,item,title,context):
        from api.openlibrary import OpenLibraryClient
        body = self._call('openlibrary','GET','https://openlibrary.org/search.json',context,
                          params={'q':title+' '+str(item.metadata.get('author','')),'limit':10,'fields':'key,title,author_name,first_publish_year,isbn,subject,cover_i'})
        rows = []
        for r in body['docs']:
            series,index = OpenLibraryClient._extract_series(r.get('subject',[]))
            rows.append((r.get('key'),r.get('title'),r.get('first_publish_year'),{'author':', '.join(r.get('author_name',[])),'isbn':(r.get('isbn') or [''])[0],
                         'series':series,'series_index':index,'poster_url':f"https://covers.openlibrary.org/b/id/{r['cover_i']}-M.jpg" if r.get('cover_i') else ''}))
        return rows

    def _acoustid(self,item,title,context):
        if not self.config.get_pref('fingerprint_enabled',False):
            raise ProviderError('consent_required','acoustid')
        key = self._key('acoustid')
        from api.acoustid import fingerprint_file, fpcalc_available
        if not fpcalc_available():
            raise ProviderError('fpcalc_required','acoustid')
        fingerprint = fingerprint_file(item.path)
        if context.cancelled(): raise Cancelled()
        if not fingerprint:
            raise ProviderError('fingerprint_failed','acoustid')
        body = self._call('acoustid','POST','https://api.acoustid.org/v2/lookup',context,
                          data={'client':key,'meta':'recordings','fingerprint':fingerprint[0],'duration':fingerprint[1]})
        if body.get('status') != 'ok':
            raise ProviderError('provider_unavailable','acoustid')
        matches = []
        for result in body.get('results',[])[:6]:
            for recording in result.get('recordings',[])[:2]:
                full = self._call('musicbrainz','GET','https://musicbrainz.org/ws/2/recording/'+recording['id'],context,
                                  params={'inc':'artists+releases+release-groups','fmt':'json'})
                rid,name,year,metadata = self._recording(full)
                matches.append((rid,name,year,{**metadata,'fingerprint_score':result.get('score')}))
        return matches

    def _audd(self,item,title,context):
        if not self.config.get_pref('audd_enabled',False):
            raise ProviderError('consent_required','audd')
        key = self._key('audd')
        with Path(item.path).open('rb') as file:
            sample = file.read(512*1024)
        body = self._call('audd','POST','https://api.audd.io/',context,data={'api_token':key,'return':'apple_music,spotify'},files={'file':('audio',sample,'application/octet-stream')})
        if body.get('status') != 'success':
            raise ProviderError('provider_unavailable','audd')
        r = body.get('result')
        return [] if not r else [(r.get('song_link',''),r.get('title'),r.get('release_date','')[:4],{'artist':r.get('artist',''),'album':r.get('album',''),'song_link':r.get('song_link','')})]

    def _anidb(self,item,title,context):
        # The legacy client's search parameters are not a documented HTTP API.
        # Title catalogue search is implemented separately with a daily cache.
        from orion.anidb_titles import search_titles
        return [(r['id'],r['title'],'',{}) for r in search_titles(title,self.config,context)]
