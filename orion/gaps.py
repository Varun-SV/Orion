"""Episode completeness against a confirmed, cached TMDb series mapping."""
import json
import threading
import time
from datetime import date
import requests
from pydantic import Field
from orion.models import Record
from orion.providers import ProviderError
from orion.discovery import Cancelled
from orion.store import utcnow

class ProviderMapping(Record):
    provider:str='tmdb'
    provider_id:str=Field(pattern=r'^[1-9][0-9]{0,9}$')
    confirmed:bool=False
class GapReport(Record):
    state:str
    missing:list[tuple[int,int]]=Field(default_factory=list)
    unaired:list[tuple[int,int]]=Field(default_factory=list)
    unknown_air_date:list[tuple[int,int]]=Field(default_factory=list)
    present:list[tuple[int,int]]=Field(default_factory=list)
    episodes:list[dict]=Field(default_factory=list)
    error:str|None=None
    catalogue_cached:bool=False
    catalogue_updated_at:str=''

class TmdbCatalogue:
    def __init__(self,store,providers,clock=time.time):
        self.store,self.providers,self.clock=store,providers,clock
        self._lock=threading.Lock()

    def get_cached(self,path):
        """Read fresh catalogue data without network I/O or the fetch lock."""
        with self.store.transaction() as conn:
            row=conn.execute('SELECT value FROM orion_settings WHERE key=?',('catalogue_tmdb_'+path,)).fetchone()
        if not row:
            return None
        try:
            cached=json.loads(row[0])
            if self.clock()-cached['time']>=3600 or not isinstance(cached['data'],dict) or cached['data'].get('success') is False:
                return None
            return cached['data'],True,cached['updated_at']
        except (ValueError,TypeError,KeyError):
            return None

    def _get(self,path,context):
        key='catalogue_tmdb_'+path
        with self._lock:
            with self.store.transaction() as conn:
                row=conn.execute('SELECT value FROM orion_settings WHERE key=?',(key,)).fetchone()
            cached=json.loads(row[0]) if row else None
            if cached and self.clock()-cached['time']<3600:
                return cached['data'],True,cached['updated_at']
            try:
                data=self.providers._call('tmdb','GET','https://api.themoviedb.org/3/'+path,context,params={'api_key':self.providers._key('tmdb'),'language':'en-US'})
                if not isinstance(data,dict) or data.get('success') is False:raise ProviderError('provider_unavailable','tmdb')
            except (ProviderError,Cancelled):raise
            except requests.HTTPError as exc:
                code='credentials_invalid' if exc.response is not None and exc.response.status_code in (401,403) else 'provider_unavailable'
                raise ProviderError(code,'tmdb') from None
            except (requests.RequestException,ValueError,TypeError):raise ProviderError('provider_unavailable','tmdb') from None
            updated=utcnow()
            with self.store.transaction() as conn:
                conn.execute('INSERT OR REPLACE INTO orion_settings VALUES(?,?)',(key,json.dumps({'time':self.clock(),'updated_at':updated,'data':data})))
            return data,False,updated

    def episodes(self,provider_id,include_specials,context):
        if not str(provider_id).isdigit():raise ValueError('Use a numeric TMDb series ID')
        series,cached,updated=self._get('tv/'+provider_id,context)
        seasons=series.get('seasons')
        if not isinstance(seasons,list) or len(seasons)>1000:raise ProviderError('invalid_catalogue','tmdb')
        episodes=[]
        for season in seasons:
            if not isinstance(season,dict):raise ProviderError('invalid_catalogue','tmdb')
            number=season.get('season_number')
            if not isinstance(number,int) or number<0:raise ProviderError('invalid_catalogue','tmdb')
            if number==0 and not include_specials:continue
            data,hit,timestamp=self._get(f'tv/{provider_id}/season/{number}',context)
            cached=cached and hit;updated=min(updated,timestamp)
            members=data.get('episodes')
            if not isinstance(members,list) or len(members)>10000:raise ProviderError('invalid_catalogue','tmdb')
            declared=season.get('episode_count')
            if declared is not None and (type(declared) is not int or declared<0 or len(members)!=declared):raise ProviderError('incomplete_catalogue','tmdb')
            numbers=[e.get('episode_number') for e in members if isinstance(e,dict)]
            if any(type(n) is not int for n in numbers) or len(set(numbers))!=len(members):raise ProviderError('invalid_catalogue','tmdb')
            for episode in members:
                if not isinstance(episode,dict) or not isinstance(episode.get('episode_number'),int) or episode['episode_number']<1:raise ProviderError('invalid_catalogue','tmdb')
                episodes.append({'season':number,'episode':episode['episode_number'],'air_date':episode.get('air_date') or '',
                    'title':episode.get('name',''),'plot':episode.get('overview',''),'provider_id':str(episode.get('id','')),'still_path':episode.get('still_path','')})
            context.progress('Reading episode catalogue',len(episodes),len(episodes))
        return {'episodes':episodes,'cached':cached,'updated_at':updated}

class EpisodeGaps:
    def __init__(self,server,catalogue,today=date.today):
        self.server,self.catalogue,self.today=server,catalogue,today

    def compare(self,series_id,provider_mapping,include_specials,context):
        if not provider_mapping.confirmed or provider_mapping.provider!='tmdb':return GapReport(state='mapping_required')
        try:
            actual=self.server.episodes(series_id,context)
            catalogue=self.catalogue.episodes(provider_mapping.provider_id,include_specials,context)
            present=set()
            for episode in actual:
                end=episode.episode_end or episode.episode
                if end<episode.episode or end-episode.episode>100:raise ProviderError('episode_number_unavailable','media_server')
                present.update((episode.season,e) for e in range(episode.episode,end+1))
            report=GapReport(state='ready',present=sorted(present),catalogue_cached=catalogue['cached'],catalogue_updated_at=catalogue['updated_at'])
            for episode in catalogue['episodes']:
                pair=(episode['season'],episode['episode'])
                if pair[0]==0 and not include_specials:continue
                state='present'
                if pair not in present:
                    try:air=date.fromisoformat(episode['air_date'])
                    except (ValueError,TypeError):
                        report.unknown_air_date.append(pair);state='unknown_air_date'
                    else:
                        state='unaired' if air>self.today() else 'missing'
                        (report.unaired if state=='unaired' else report.missing).append(pair)
                report.episodes.append({**episode,'state':state})
            report.missing=sorted(set(report.missing));report.unaired=sorted(set(report.unaired));report.unknown_air_date=sorted(set(report.unknown_air_date))
            return report
        except Cancelled:raise
        except ProviderError as exc:return GapReport(state='unavailable',error=exc.code)
