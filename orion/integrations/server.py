"""Bounded Jellyfin/Emby transport with explicit user context and complete pagination."""
from __future__ import annotations
import json
import re
import time
from urllib.parse import urlsplit,urlunsplit,quote
import requests
from pydantic import Field
from orion.models import Record
from orion.providers import ProviderError
from orion.discovery import Cancelled

class ServerError(ProviderError):
    def __init__(self,code):super().__init__(code,'media_server')

class ServerInfo(Record):
    id:str
    name:str
    version:str
class ServerUser(Record):
    id:str
    name:str
class ServerQuery(Record):
    search:str=Field(default='',max_length=200)
    include_types:str='Movie,Series,Audio,MusicAlbum,Book'
    parent_id:str=''
class ServerItem(Record):
    id:str
    name:str
    type:str
    year:int|None=None
    path:str=''
    resolution:str=''
    edition:str=''
    is_virtual:bool=False
    provider_ids:dict[str,str]=Field(default_factory=dict)
    media_sources:list[dict]=Field(default_factory=list)
    season:int|None=None
    episode:int|None=None
    episode_end:int|None=None
class ServerEpisode(Record):
    id:str
    name:str
    season:int
    episode:int
    episode_end:int|None=None
class RefreshResult(Record):
    accepted:bool=True
    detail:str='Server accepted the refresh request; completion is managed by the server.'

def server_url(url):
    parsed=urlsplit(url.strip())
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or '\\' in url or any(ord(c)<32 for c in url):
        raise ValueError('Use an HTTP(S) server URL without credentials, query parameters or fragments')
    try:parsed.port
    except ValueError:raise ValueError('Invalid server port') from None
    return url.strip().rstrip('/')

class MediaServerClient:
    def __init__(self,base_url,api_key,server_type='jellyfin',user_id=None):
        self.base=server_url(base_url)
        if server_type not in ('jellyfin','emby'):raise ValueError('Choose Jellyfin or Emby')
        self.server_type,self.key,self.user_id=server_type,api_key,user_id
        self._session=requests.Session()
        self._session.trust_env=False

    def _call(self,method,path,context,params=None):
        if context.cancelled():raise Cancelled()
        if not self.key:raise ServerError('server_credentials_required')
        headers={'X-Emby-Token':self.key,'Accept':'application/json','User-Agent':'Orion/0.2'}
        if self.server_type=='jellyfin':
            headers['Authorization']='MediaBrowser Client="Orion", Version="0.2", Token="'+quote(self.key,safe='')+'"'
        try:
            with self._session.request(method,self.base+path,params=params or {},
                headers=headers,
                timeout=(3,10),allow_redirects=False,stream=True) as response:
                if response.status_code in (401,403):raise ServerError('server_unauthorised')
                if not 200<=response.status_code<300:raise ServerError('server_unavailable')
                if method=='POST':return {}
                content=bytearray();deadline=time.monotonic()+30
                for block in response.iter_content(65536):
                    if context.cancelled():raise Cancelled()
                    if time.monotonic()>deadline or len(content)+len(block)>16*1024*1024:raise ServerError('server_response_limit')
                    content.extend(block)
                return json.loads(content)
        except (ServerError,Cancelled):raise
        except requests.RequestException:raise ServerError('server_unavailable') from None
        except (ValueError,TypeError):raise ServerError('invalid_server_response') from None

    def test_connection(self,context):
        data=self._call('GET','/System/Info',context)
        if not isinstance(data,dict) or not data.get('ServerName') or not data.get('Version'):raise ServerError('invalid_server_response')
        return ServerInfo(id=str(data.get('Id','')),name=str(data['ServerName']),version=str(data['Version']))

    def users(self,context):
        data=self._call('GET','/Users',context)
        if not isinstance(data,list) or len(data)>10000:raise ServerError('invalid_server_response')
        if any(not isinstance(user,dict) or not user.get('Id') or not user.get('Name') for user in data):raise ServerError('invalid_server_response')
        return [ServerUser(id=str(user['Id']),name=str(user['Name'])) for user in data]

    @staticmethod
    def parse(item):
        if not isinstance(item,dict) or not item.get('Id'):raise ServerError('invalid_server_response')
        sources=item.get('MediaSources') or []
        streams=item.get('MediaStreams') or []
        if not isinstance(sources,list) or not all(isinstance(s,dict) for s in sources):raise ServerError('invalid_server_response')
        for source in sources:streams=streams+(source.get('MediaStreams') or [])
        try:
            height=max([int(s.get('Height') or 0) for s in streams if s.get('Type')=='Video'] or [0])
            ids=item.get('ProviderIds') or {}
            if not isinstance(ids,dict):raise ValueError()
            stream_keys={'Type','Index','Codec','Height','Width','BitRate','BitDepth','Channels','ChannelLayout','Language','IsDefault','IsForced'}
            cleaned_sources=[]
            for source in sources:
                cleaned={key:source[key] for key in ('Id','Name','Container','Size','Bitrate') if key in source}
                cleaned['MediaStreams']=[{key:value for key,value in stream.items() if key in stream_keys} for stream in (source.get('MediaStreams') or []) if isinstance(stream,dict)]
                cleaned_sources.append(cleaned)
            path=str(item.get('Path',''))
            if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*://',path):
                location=urlsplit(path)
                host=location.hostname or ''
                if ':' in host:host='['+host+']'
                path=urlunsplit((location.scheme,host+(':'+str(location.port) if location.port else ''),location.path,'',''))
            return ServerItem(id=str(item['Id']),name=str(item.get('Name','')),type=str(item.get('Type','')),year=item.get('ProductionYear'),
                path=path,resolution=f'{height}p' if height else '',provider_ids={str(k).lower():str(v) for k,v in ids.items() if str(k).lower() in {'tmdb','imdb','tvdb','anidb','anilist','tvmaze','musicbrainz','musicbrainzalbum','musicbrainzartist','musicbrainztrack','musicbrainzreleasegroup','isbn'}},
                edition=str(item.get('Edition') or ' · '.join(str(s.get('Name','')) for s in sources if s.get('Name'))),is_virtual=bool(item.get('IsVirtualItem') or item.get('IsMissing')),
                media_sources=cleaned_sources,season=item.get('ParentIndexNumber'),episode=item.get('IndexNumber'),episode_end=item.get('IndexNumberEnd'))
        except (TypeError,ValueError,AttributeError):raise ServerError('invalid_server_response') from None

    def items(self,query:ServerQuery,context):
        if not self.user_id:raise ServerError('server_user_context_required')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',str(self.user_id)):raise ValueError('Invalid server user ID')
        params={'UserId':self.user_id,'Recursive':'true','IncludeItemTypes':query.include_types,'Fields':'ProviderIds,Path,MediaSources,MediaStreams',
            'SortBy':'SortName','SortOrder':'Ascending','Limit':50,'EnableTotalRecordCount':'true','EnableImages':'false'}
        if query.search:params['SearchTerm']=query.search
        if query.parent_id:params['ParentId']=query.parent_id
        if query.include_types=='Episode':params.update(IsMissing='false',ExcludeLocationTypes='Virtual')
        records,seen,total=[],set(),None
        for page in range(2000):
            params['StartIndex']=len(records)
            data=self._call('GET','/Items',context,params)
            if not isinstance(data,dict) or not isinstance(data.get('Items'),list):raise ServerError('invalid_server_response')
            declared=data.get('TotalRecordCount')
            if declared is not None:
                if not isinstance(declared,int) or declared<0 or declared>100000:raise ServerError('server_response_limit')
                if total is not None and declared!=total:raise ServerError('incomplete_pagination')
                total=declared
            raw=data['Items']
            if not raw:
                if total is not None and len(records)<total:raise ServerError('incomplete_pagination')
                return records
            for item in raw:
                parsed=self.parse(item)
                if parsed.id in seen:raise ServerError('incomplete_pagination')
                seen.add(parsed.id);records.append(parsed)
            context.progress('Reading server library',len(records),total or len(records))
            if total is not None and len(records)>=total:
                if len(records)!=total:raise ServerError('incomplete_pagination')
                return records
            if total is None and len(raw)<50:return records
        raise ServerError('server_response_limit')

    def episodes(self,series_id,context):
        episodes=self.items(ServerQuery(include_types='Episode',parent_id=series_id),context)
        episodes=[e for e in episodes if not e.is_virtual]
        if any(e.type!='Episode' or e.season is None or e.episode is None or e.season<0 or e.episode<1 for e in episodes):raise ServerError('episode_number_unavailable')
        return [ServerEpisode(id=e.id,name=e.name,season=e.season,episode=e.episode,episode_end=e.episode_end) for e in episodes]

    def refresh(self,context):
        self._call('POST','/Library/Refresh',context)
        return RefreshResult()
