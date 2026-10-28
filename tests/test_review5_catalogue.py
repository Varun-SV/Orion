import json
import xml.etree.ElementTree as ET

import pytest

from orion.config import Config
from orion.discovery import signature, parsed_metadata
from orion.gaps import TmdbCatalogue
from orion.models import MediaItem, MatchDecision
from orion.naming import NamingProfile
from orion.planner import Planner, PlanOptions
from orion.providers import Providers
from orion.store import item_id


def series_plan(library, tmp_path, seasons, provider='tmdb'):
    root = tmp_path / 'incoming'
    root.mkdir()
    sid = library.add_source(root, kind='series')['id']
    ids = []
    for index, (provider_id, season) in enumerate(seasons):
        media = root / f'Original{index}.S{season:02d}E{index+1:02d}.mkv'
        media.write_bytes(b'episode')
        iid = 'episode-' + str(index)
        decision = MatchDecision(item_id=iid, provider=provider, provider_id=provider_id, metadata={'title':'Show ' + provider_id, 'year':'2020'})
        library.upsert(MediaItem(id=iid, source_id=sid, path=str(media), kind='series', status='approved', signature=signature(media), metadata=parsed_metadata(media, 'series'), decision=decision))
        ids.append(iid)
    destination = tmp_path / 'library'
    destination.mkdir()
    did = item_id('destination', destination)
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)', (did, str(destination), 'Library'))
    return Planner(library), ids, PlanOptions(destination_id=did, profile=NamingProfile(episode_nfo_enabled=True))


def episode_outputs(plan):
    return [ET.fromstring(op.verification['content']) for op in plan.operations if op.kind == 'create_nfo']


class PreviewCatalogue:
    def __init__(self, data=None):
        self.data = data or {}
        self.external_calls = []
        self.cache_calls = []

    def _get(self, path, context):
        self.external_calls.append(path)
        return self.data.get(path, {'episodes':[]}), False, 'now'

    def get_cached(self, path):
        self.cache_calls.append(path)
        data = self.data.get(path)
        return (data, True, 'now') if data is not None else None


def test_many_series_and_seasons_have_zero_aggregate_external_preview_calls(library, tmp_path):
    planner, ids, options = series_plan(library, tmp_path, [(str(100+i), i+1) for i in range(25)])
    planner.catalogue = PreviewCatalogue()
    plan = planner.create(ids, options)
    assert not plan.issues
    assert planner.catalogue.external_calls == []
    outputs = episode_outputs(plan)
    assert len(outputs) == len(ids)
    assert all(node.find('uniqueid') is None for node in outputs)
    assert {warning.item_id for warning in plan.warnings if warning.code == 'episode_metadata_unavailable'} == set(ids)


def test_repeated_series_season_cache_is_read_once_across_items(library, tmp_path):
    planner, ids, options = series_plan(library, tmp_path, [('123', 1)] * 3)
    path = 'tv/123/season/1'
    planner.catalogue = PreviewCatalogue({path:{'episodes':[{'episode_number':n, 'name':f'Cached episode {n}', 'id':100+n} for n in (1,2,3)]}})
    plan = planner.create(ids, options)
    assert not plan.issues
    assert planner.catalogue.external_calls == []
    assert planner.catalogue.cache_calls == [path]
    outputs = episode_outputs(plan)
    assert {node.findtext('title') for node in outputs} == {'Cached episode 1', 'Cached episode 2', 'Cached episode 3'}
    assert {node.findtext('uniqueid') for node in outputs} == {'101', '102', '103'}
    assert not any(w.code == 'episode_metadata_unavailable' for w in plan.warnings)


@pytest.mark.parametrize('cache_state', ['missing', 'expired', 'corrupt'])
def test_unavailable_cache_never_enters_transport_or_retry_and_warns(library, tmp_path, cache_state):
    planner, ids, options = series_plan(library, tmp_path, [('123', 1)])
    calls = []
    config = Config(tmp_path / 'prefs')
    config.set_api_key('tmdb', 'fixture-key', session_only=True)
    def transport(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError('Preview must not enter transport, timeout, or retry')
    planner.catalogue = TmdbCatalogue(library.store, Providers(config, request=transport), clock=lambda:7200)
    if cache_state != 'missing':
        value = 'broken-json' if cache_state == 'corrupt' else json.dumps({'time':0, 'updated_at':'then', 'data':{'episodes':[{'episode_number':1, 'id':999}]}})
        with library.store.transaction() as conn:
            conn.execute('INSERT INTO orion_settings VALUES(?,?)', ('catalogue_tmdb_tv/123/season/1', value))
    plan = planner.create(ids, options)
    assert not plan.issues and calls == []
    assert len(episode_outputs(plan)) == 1
    assert episode_outputs(plan)[0].find('uniqueid') is None
    assert any(w.code == 'episode_metadata_unavailable' for w in plan.warnings)


def test_fresh_persisted_catalogue_enriches_preview_without_network_lock(library, tmp_path):
    planner, ids, options = series_plan(library, tmp_path, [('123', 1)])
    planner.catalogue = TmdbCatalogue(library.store, Providers(Config(tmp_path / 'prefs')), clock=lambda:7200)
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_settings VALUES(?,?)', ('catalogue_tmdb_tv/123/season/1', json.dumps({'time':7100, 'updated_at':'recent', 'data':{'episodes':[{'episode_number':1, 'name':'Cached title', 'overview':'Cached plot', 'id':101}]}})))
    class NetworkLock:
        def __enter__(self):
            raise AssertionError('Preview waited for the network catalogue lock')
        def __exit__(self, *args):
            pass
    planner.catalogue._lock = NetworkLock()
    plan = planner.create(ids, options)
    assert not plan.issues
    output = episode_outputs(plan)[0]
    assert output.findtext('title') == 'Cached title'
    assert output.findtext('uniqueid') == '101'
    assert not any(w.code == 'episode_metadata_unavailable' for w in plan.warnings)


@pytest.mark.parametrize('has_catalogue', [False, True])
def test_unavailable_episode_metadata_has_explicit_fallback_warning(library, tmp_path, has_catalogue):
    planner, ids, options = series_plan(library, tmp_path, [('123', 1)])
    if has_catalogue:
        planner.catalogue = PreviewCatalogue({'tv/123/season/1':{'episodes':[]}})
    plan = planner.create(ids, options)
    assert not plan.issues
    output = episode_outputs(plan)[0]
    assert output.findtext('showtitle') == 'Show 123'
    assert output.findtext('season') == '1' and output.findtext('episode') == '1'
    assert output.find('uniqueid') is None
    assert any(w.code == 'episode_metadata_unavailable' for w in plan.warnings)


def test_ordinary_preview_performs_no_catalogue_io(library, tmp_path):
    planner, ids, options = series_plan(library, tmp_path, [('123', 1)])
    planner.catalogue = PreviewCatalogue()
    options.profile.episode_nfo_enabled = False
    plan = planner.create(ids, options)
    assert not plan.issues
    assert planner.catalogue.external_calls == planner.catalogue.cache_calls == []
    assert not episode_outputs(plan)