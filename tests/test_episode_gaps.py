from datetime import date
import pytest
from orion.gaps import EpisodeGaps,ProviderMapping,TmdbCatalogue
from orion.integrations.server import ServerEpisode,ServerError
from orion.providers import Providers,ProviderError
from orion.config import Config

class Server:
    def __init__(self,offline=False):self.offline=offline
    def episodes(self,series_id,context):
        if self.offline:raise ServerError('server_unavailable')
        return [ServerEpisode(id='one',name='one',season=1,episode=1,episode_end=2)]
class Catalogue:
    def __init__(self,fail=False):self.fail=fail
    def episodes(self,provider_id,include_specials,context):
        if self.fail:raise ProviderError('provider_unavailable','tmdb')
        return {'episodes':[{'season':0,'episode':1,'air_date':'2020-01-01'},{'season':1,'episode':1,'air_date':'2020-01-01'},{'season':1,'episode':2,'air_date':'2020-01-01'},{'season':1,'episode':3,'air_date':'2020-01-01'},{'season':1,'episode':4,'air_date':'2099-01-01'},{'season':1,'episode':5,'air_date':''}], 'cached':False,'updated_at':'2026-10-09'}

def test_gaps_use_confirmed_mapping_exclude_specials_and_separate_unknown_dates(context):
    report=EpisodeGaps(Server(),Catalogue(),today=lambda:date(2026,10,9)).compare('series',ProviderMapping(provider_id='42',confirmed=True),False,context)
    assert report.state=='ready'
    assert report.missing==[(1,3)] and report.unaired==[(1,4)]
    assert report.unknown_air_date==[(1,5)]
    assert EpisodeGaps(Server(),Catalogue()).compare('series',ProviderMapping(provider_id='42',confirmed=True),True,context).missing==[(0,1),(1,3)]

@pytest.mark.parametrize('server,catalogue',[(Server(True),Catalogue()),(Server(),Catalogue(True))])
def test_unavailable_server_or_catalogue_never_declares_missing_season(context,server,catalogue):
    report=EpisodeGaps(server,catalogue).compare('series',ProviderMapping(provider_id='42',confirmed=True),False,context)
    assert report.state=='unavailable' and report.missing==[]

def test_ambiguous_mapping_requires_confirmation_before_catalogue_request(context):
    report=EpisodeGaps(Server(),Catalogue()).compare('series',ProviderMapping(provider_id='42',confirmed=False),False,context)
    assert report.state=='mapping_required' and report.missing==[]

def test_cached_season_catalogue_uses_one_call_per_season_not_episode(library,tmp_path,context):
    config=Config(tmp_path/'prefs');config.set_api_key('tmdb','key',session_only=True)
    calls=[]
    def request(provider,method,url,ctx,**kwargs):
        calls.append(url)
        if '/season/' not in url:return {'seasons':[{'season_number':0},{'season_number':1}]}
        return {'episodes':[{'season_number':1,'episode_number':i,'air_date':'2020-01-01','name':str(i),'overview':'Plot'} for i in range(1,126)]}
    catalogue=TmdbCatalogue(library.store,Providers(config,request=request))
    first=catalogue.episodes('42',False,context);second=catalogue.episodes('42',False,context)
    assert len(first['episodes'])==125 and second['cached'] is True
    assert len(calls)==2

def test_incomplete_catalogue_is_unavailable_and_does_not_fake_complete_season(library,tmp_path,context):
    config=Config(tmp_path/'prefs');config.set_api_key('tmdb','key',session_only=True)
    def request(provider,method,url,ctx,**kwargs):
        return {'seasons':[{'season_number':1,'episode_count':12}]} if '/season/' not in url else {'episodes':[]}
    report=EpisodeGaps(Server(),TmdbCatalogue(library.store,Providers(config,request=request))).compare('series',ProviderMapping(provider_id='42',confirmed=True),False,context)
    assert report.state=='unavailable' and report.missing==[]

def test_gap_results_preserve_episode_title_air_date_and_presence(context):
    class Details(Catalogue):
        def episodes(self,*args):
            data=super().episodes(*args)
            for ep in data['episodes']:ep['title']='Episode '+str(ep['episode'])
            return data
    result=EpisodeGaps(Server(),Details()).compare('series',ProviderMapping(provider_id='42',confirmed=True),False,context)
    missing=next(ep for ep in result.episodes if ep['season']==1 and ep['episode']==3)
    assert missing['title']=='Episode 3' and missing['air_date']=='2020-01-01' and missing['state']=='missing'
    assert next(ep for ep in result.episodes if ep['episode']==1)['state']=='present'
