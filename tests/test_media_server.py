import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
import pytest
from orion.integrations.server import MediaServerClient,ServerQuery,ServerError

@pytest.fixture
def server_fixture():
    state={'requests':[],'status':200,'repeat':False,'redirect':False}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            parsed=urlsplit(self.path);q=parse_qs(parsed.query)
            state['requests'].append((parsed.path,q,dict(self.headers)))
            status=302 if state['redirect'] else state['status']
            if state.get('modern_auth') and not self.headers.get('Authorization','').startswith('MediaBrowser '):status=401
            if parsed.path.endswith('/System/Info'):body={'ServerName':'Fixture','Version':'12.0','Id':'fixture'}
            elif parsed.path.endswith('/Users'):body=[{'Id':'chosen-user','Name':'My user'},{'Id':'other','Name':'Other'}]
            else:
                start=0 if state['repeat'] else int(q.get('StartIndex',['0'])[0]);limit=int(q.get('Limit',['50'])[0]);episode=q.get('IncludeItemTypes')==['Episode']
                body={'TotalRecordCount':125,'Items':[{'Id':str(i),'Name':'Arrival','Type':'Episode' if episode else 'Movie','ProviderIds':{'Tmdb':'329865'},'ProductionYear':2016,'Path':f'/media/{i}.mkv','ParentIndexNumber':1,'IndexNumber':i+1,'MediaSources':[{'MediaStreams':[{'Type':'Video','Height':2160,'Codec':'hevc'}]}]} for i in range(start,min(start+limit,125))]}
            self.send_response(status)
            if status==302:self.send_header('Location','http://127.0.0.1:1/leak')
            self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(body).encode())
        def do_POST(self):
            state['requests'].append((self.path,{},dict(self.headers)))
            self.send_response(204 if state['status']==200 else state['status']);self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',state
    server.shutdown();server.server_close();thread.join()

@pytest.mark.parametrize('kind',['jellyfin','emby'])
def test_real_http_servers_paginate_preserve_metadata_and_use_header_key(server_fixture,context,kind):
    url,state=server_fixture
    client=MediaServerClient(url,'private-server-key',kind,user_id='chosen-user')
    assert client.test_connection(context).name=='Fixture'
    assert client.users(context)[0].id=='chosen-user'
    items=client.items(ServerQuery(),context)
    assert len(items)==125 and items[0].resolution=='2160p'
    assert items[0].provider_ids=={'tmdb':'329865'}
    assert items[0].media_sources[0]['MediaStreams'][0]['Codec']=='hevc'
    episodes=client.episodes('series',context)
    assert len(episodes)==125 and episodes[-1].episode==125
    assert client.refresh(context).accepted is True
    pages=[q for path,q,h in state['requests'] if path.endswith('/Items') and q.get('IncludeItemTypes')!=['Episode']]
    assert [int(q['StartIndex'][0]) for q in pages]==[0,50,100]
    assert all(h.get('X-Emby-Token')=='private-server-key' for path,q,h in state['requests'])
    assert all('api_key' not in q for path,q,h in state['requests'])
    assert not any('/Items/' in p for p,q,h in state['requests']) # no per-item metadata requests

@pytest.mark.parametrize('status,code',[(401,'server_unauthorised'),(403,'server_unauthorised'),(500,'server_unavailable')])
def test_failure_is_never_an_empty_library(server_fixture,context,status,code):
    url,state=server_fixture;state['status']=status
    with pytest.raises(ServerError) as error:MediaServerClient(url,'key',user_id='chosen-user').items(ServerQuery(),context)
    assert error.value.code==code and 'key' not in str(error.value)

def test_explicit_user_context_required_before_library_request(server_fixture,context):
    url,state=server_fixture
    with pytest.raises(ServerError,match='user context'):MediaServerClient(url,'key').items(ServerQuery(),context)
    assert state['requests']==[]

def test_repeated_pagination_and_redirects_are_unavailable_not_truncated_success(server_fixture,context):
    url,state=server_fixture;state['repeat']=True
    with pytest.raises(ServerError) as error:MediaServerClient(url,'key',user_id='chosen-user').items(ServerQuery(),context)
    assert error.value.code=='incomplete_pagination'
    state['redirect']=True
    with pytest.raises(ServerError):MediaServerClient(url,'key').test_connection(context)

@pytest.mark.parametrize('url',['file:///etc/passwd','http://user:key@host:8096','http://host:8096?api_key=secret','http://host:8096/#fragment'])
def test_server_url_rejects_embedded_credentials_and_unsupported_schemes(url):
    with pytest.raises(ValueError):MediaServerClient(url,'key')

def test_server_results_strip_transport_credentials_and_remote_url_secrets(server_fixture,context,monkeypatch):
    url,state=server_fixture
    client=MediaServerClient(url,'key',user_id='chosen-user')
    raw={'Id':'remote','Name':'Example','Type':'Movie','Path':'https://user:password@stream.example/video?api_key=private',
         'MediaSources':[{'Id':'source','AccessToken':'private','HttpHeaders':{'Authorization':'private'},'MediaStreams':[{'Type':'Video','Height':1080,'Codec':'h264','Token':'private'}]}]}
    monkeypatch.setattr(client,'_call',lambda *a,**k:{'Items':[raw],'TotalRecordCount':1})
    result=client.items(ServerQuery(),context)[0]
    assert 'private' not in result.model_dump_json() and 'password' not in result.model_dump_json()
    assert result.resolution=='1080p'

def test_jellyfin_authentication_works_with_legacy_headers_disabled(server_fixture,context):
    url,state=server_fixture;state['modern_auth']=True
    assert MediaServerClient(url,'private-key','jellyfin').test_connection(context).name=='Fixture'
    headers=state['requests'][0][2]
    assert 'Token="private-key"' in headers['Authorization']

def test_server_version_labels_survive_but_unknown_provider_secrets_do_not(server_fixture,context,monkeypatch):
    url,state=server_fixture;client=MediaServerClient(url,'key',user_id='chosen-user')
    raw={'Id':'edition','Name':'Arrival','Type':'Movie','ProviderIds':{'Tmdb':'329865','api_key':'private'},'MediaSources':[{'Name':'Directors cut','MediaStreams':[]}]}
    monkeypatch.setattr(client,'_call',lambda *a,**k:{'Items':[raw],'TotalRecordCount':1})
    result=client.items(ServerQuery(),context)[0]
    assert result.edition=='Directors cut'
    assert result.provider_ids=={'tmdb':'329865'}

def test_virtual_placeholder_episode_is_not_counted_as_an_existing_file(server_fixture,context,monkeypatch):
    url,state=server_fixture;client=MediaServerClient(url,'key',user_id='chosen-user')
    raw=[{'Id':'virtual','Name':'Missing','Type':'Episode','ParentIndexNumber':1,'IndexNumber':3,'IsVirtualItem':True}, {'Id':'real','Name':'Present','Type':'Episode','ParentIndexNumber':1,'IndexNumber':1}]
    monkeypatch.setattr(client,'_call',lambda *a,**k:{'Items':raw,'TotalRecordCount':2})
    result=client.episodes('series',context)
    assert [(e.season,e.episode) for e in result]==[(1,1)]
