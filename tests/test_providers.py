import time
import threading
import pytest
import requests
from orion.providers import Providers, ProviderError, RateLimiter
from orion.config import Config
from orion.models import MediaItem

def film():
    return MediaItem(id='film',source_id='a',path='film.mkv',kind='movies',metadata={'title':'Arrival','year':'2016'})

def test_candidate_evidence_is_not_popularity_confidence(tmp_path, context):
    config = Config(tmp_path)
    config.set_api_key('tmdb','test-key',session_only=True)
    def request(*a,**kw):
        return {'results':[{'id':329865,'title':'Arrival','release_date':'2016-11-10','overview':'Plot','poster_path':'/cover.jpg','vote_average':8.1}]}
    result = Providers(config,request=request).candidates(film(),context)
    assert result[0].provider_id == '329865'
    assert result[0].metadata['plot'] == 'Plot'
    assert 'Title agrees with parsed metadata' in result[0].evidence
    assert not hasattr(result[0], 'confidence')
    assert 'test-key' not in result[0].model_dump_json()

def test_no_match_and_unavailable_are_distinct(tmp_path, context):
    cfg = Config(tmp_path)
    cfg.set_api_key('tmdb','key',session_only=True)
    assert Providers(cfg,request=lambda *a,**k:{'results':[]}).candidates(film(),context) == []
    def offline(*a,**k):
        raise requests.ConnectionError('sensitive-url?api_key=secret')
    with pytest.raises(ProviderError) as exc:
        Providers(cfg,request=offline).candidates(film(),context)
    assert exc.value.code == 'provider_unavailable'
    assert 'secret' not in str(exc.value)

def test_missing_key_is_configuration_error(tmp_path, context):
    with pytest.raises(ProviderError) as exc:
        Providers(Config(tmp_path)).candidates(film(),context)
    assert exc.value.code == 'credentials_required'

def test_global_rate_limit_spaces_competing_requests(context):
    limiter = RateLimiter({'fixture':0.03})
    started = []
    def go():
        limiter.acquire('fixture',context)
        started.append(time.monotonic())
    threads = [threading.Thread(target=go) for _ in range(3)]
    for t in threads: t.start()
    for t in threads: t.join()
    ordered = sorted(started)
    assert ordered[1]-ordered[0] >= 0.025
    assert ordered[2]-ordered[1] >= 0.025

@pytest.mark.parametrize('kind,provider,payload,identifier,title,field,value', [
 ('books','openlibrary',{'docs':[{'key':'/works/OL1W','title':'Dune','author_name':['Frank Herbert'],'first_publish_year':1965,'isbn':['123'],'cover_i':10,'subject':[]}]},'/works/OL1W','Dune','author','Frank Herbert'),
 ('music','musicbrainz',{'recordings':[{'id':'rec-1','title':'Song','artist-credit':[{'name':'Artist'}],'releases':[{'id':'release-1','title':'Album','date':'2020-01-01','media':[]}]}]},'rec-1','Song','release_mbid','release-1'),
 ('anime','anilist',{'data':{'Page':{'media':[{'id':1,'title':{'english':'Title','romaji':'Romaji','native':'Title'},'startDate':{'year':2020},'coverImage':{'medium':'https://example.com/cover'},'format':'TV','episodes':12,'averageScore':90}]}}},'1','Title','episodes',12),
])
def test_provider_metadata_survives_selection(tmp_path,context,kind,provider,payload,identifier,title,field,value):
    cfg = Config(tmp_path)
    item = MediaItem(id='item',source_id='a',path='item',kind=kind,metadata={'title':title})
    matches = Providers(cfg,request=lambda *a,**k:payload).candidates(item,context,provider=provider)
    assert matches[0].provider_id == identifier
    assert matches[0].title == title
    assert matches[0].metadata[field] == value

def test_audd_requires_explicit_audio_upload_opt_in(tmp_path,context):
    cfg = Config(tmp_path)
    cfg.set_api_key('audd','fixture',session_only=True)
    item = MediaItem(id='song',source_id='a',path='missing.mp3',kind='music',metadata={'title':'Song'})
    with pytest.raises(ProviderError) as exc:
        Providers(cfg).candidates(item,context,provider='audd')
    assert exc.value.code == 'consent_required'

from orion.models import MediaItem
from orion.config import Config
from orion.providers import Providers

def test_anidb_title_cache_search_uses_real_catalogue(tmp_path,context):
    import gzip
    cfg = Config(tmp_path)
    (tmp_path/'anidb-titles.xml.gz').write_bytes(gzip.compress(b'''<?xml version="1.0" encoding="utf-8"?>
    <animetitles><anime aid="1"><title type="main" xml:lang="x-jat">Test Anime</title><title type="official" xml:lang="en">Example Anime</title></anime><anime aid="2"><title type="main" xml:lang="x-jat">Other Show</title></anime></animetitles>'''))
    item = MediaItem(id='anime',source_id='a',path='anime.mkv',kind='anime',metadata={'title':'Example Anime'})
    matches = Providers(cfg).candidates(item,context,provider='anidb')
    assert [(r.provider_id,r.title) for r in matches] == [('1','Example Anime')]

def test_cancelled_provider_does_not_start_request(tmp_path):
    cfg = Config(tmp_path)
    cfg.set_api_key('tmdb','key',session_only=True)
    from orion.discovery import Cancelled
    class Stop:
        def cancelled(self): return True
    def forbidden(*a,**kw):
        pytest.fail('Network request started after cancellation')
    with pytest.raises(Cancelled):
        Providers(cfg,request=forbidden).candidates(film(),Stop())
