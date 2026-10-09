import sqlite3
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from orion.app import create_app
from orion.config import Config
from orion.models import MediaItem, MatchDecision
from orion.providers import Providers, ProviderError
from orion.services import Services
from orion.store import Store
from orion.profiles import Profiles
from orion.naming import valid_relative
from orion.executor import Executor
from test_sidecars import enabled_plan

@pytest.mark.parametrize('kind,provider', [('movies','audd'), ('books','acoustid'), ('music','tmdb'), ('series','anilist'), ('anime','openlibrary')])
def test_incompatible_provider_rejected_before_adapter_or_file_access(tmp_path,context,monkeypatch,kind,provider):
    cfg=Config(tmp_path)
    cfg.set_pref('audd_enabled',True)
    cfg.set_pref('fingerprint_enabled',True)
    cfg.set_pref('provider_'+kind,provider)
    engine=Providers(cfg,request=lambda *a,**k:pytest.fail('Unexpected network request'))
    monkeypatch.setattr(engine,'_'+provider,lambda *a:pytest.fail('Incompatible adapter invoked'))
    item=MediaItem(id='item',source_id='s',path='missing',kind=kind)
    for override in (provider,None):
        with pytest.raises(ProviderError) as exc:engine.candidates(item,context,provider=override)
        assert exc.value.code=='provider_incompatible'

@pytest.mark.parametrize('kind,provider', [('anime','tmdb'),('anime_films','anilist'),('music','audd'),('books','openlibrary')])
def test_compatible_providers_still_dispatch(tmp_path,context,monkeypatch,kind,provider):
    engine=Providers(Config(tmp_path))
    seen=[]
    monkeypatch.setattr(engine,'_'+provider,lambda *a:seen.append(a[0].kind) or [])
    assert engine.candidates(MediaItem(id='i',source_id='s',path='missing',kind=kind),context,provider)==[]
    assert seen==[kind]

def test_provider_preferences_and_categories_reject_incompatible_choices_atomically(tmp_path):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1:4321') as client:
        client.headers['X-Orion-CSRF']=client.get('/api/v1/session').json()['csrf_token']
        original=client.get('/api/v1/settings').json()
        response=client.put('/api/v1/settings',json={'theme':'night','providers':{'music':'musicbrainz','movies':'audd'}})
        assert response.status_code==400
        assert client.get('/api/v1/settings').json()==original
        category=next(c for c in client.get('/api/v1/categories').json() if c['kind']=='movies')
        assert category['compatible_providers']==['tmdb']
        assert client.put('/api/v1/categories/'+category['id'],json={'dest_subpath':'Films','api_pref':'audd'}).status_code==400
        assert next(c for c in client.get('/api/v1/categories').json() if c['id']==category['id'])==category
        assert client.put('/api/v1/categories/'+category['id'],json={'dest_subpath':'CON','api_pref':'tmdb'}).status_code==400

@pytest.mark.parametrize('name,kind', [('TV Shows','series'),('Japanese Cartoons','anime'),('Streaming Originals','webseries'),('Animated Features','anime_movie')])
def test_legacy_custom_category_import_uses_media_type(legacy,name,kind):
    with sqlite3.connect(legacy) as conn:
        conn.execute('INSERT INTO categories(name,media_type,api_pref,dest_subpath) VALUES(?,?,?,?)',(name,kind,'tmdb','Custom'))
        conn.execute('UPDATE scan_items SET detected_category=?',(name,))
    store=Store(legacy);backup=store.migrate()
    expected={'webseries':'web_series','anime_movie':'anime_films'}.get(kind,kind)
    with store.transaction() as conn:
        assert conn.execute('SELECT kind FROM orion_categories WHERE name=?',(name,)).fetchone()[0]==expected
        assert {r[0] for r in conn.execute("SELECT kind FROM orion_items WHERE path LIKE '%.mkv'")}=={expected}
    assert backup.is_file()

def test_first_builtin_override_advances_version_and_rejects_stale_editor(library):
    profiles=Profiles(library)
    original=profiles.get('default-movies')
    saved=profiles.save(original.model_copy(update={'movie_template':'{title}{ext}'}))
    assert saved.version==2
    assert profiles.get(original.id)==saved
    with pytest.raises(ValueError,match='version'):profiles.save(original)
    assert profiles.get(original.id)==saved

@pytest.mark.parametrize('path', ['CON','Films/nul.txt','com1/Film.mkv','LPT9.xml','AUX/Film','PRN','NUL'])
def test_portable_layout_rejects_windows_devices(path):
    with pytest.raises(ValueError,match='component'):valid_relative(path)

def test_literal_device_template_rejected_before_profile_save(library):
    profile=Profiles(library).get('default-movies')
    with pytest.raises(ValueError):Profiles(library).save(profile.model_copy(update={'movie_template':'CON/{title}{ext}'}))
    assert Profiles(library).get(profile.id)==profile

def test_cleared_decision_does_not_block_sidecar_undo(library,tmp_path,context):
    planner,plan,source=enabled_plan(library,tmp_path,context)
    executor=Executor(library,planner)
    result=executor.execute(plan.id,1,context)
    assert result.state=='completed'
    library.clear_decision(plan.operations[0].item_id)
    undo=executor.undo_plan(result.batch_id)
    assert not undo.issues
    assert any(op.kind=='remove_created' and op.verification['item_decision'] is None for op in undo.operations)
    assert executor.execute(undo.id,1,context).state=='completed'
    assert source.read_bytes()==b'original media bytes'
    assert library.get(plan.operations[0].item_id).status=='pending'
    assert all(not Path(op.destination).exists() for op in plan.operations if op.kind=='create_nfo')

@pytest.mark.parametrize('status', ['pending','approved','organised'])
def test_lookup_failure_retains_confirmed_workflow_state(library,tmp_path,context,status):
    root=tmp_path/'incoming';root.mkdir()
    source=library.add_source(root)
    item=MediaItem(id='i',source_id=source['id'],path=str(root/'a.mkv'),kind='movies',status=status,signature={'size':1},
        decision=MatchDecision(item_id='i',metadata={'title':'A'}) if status!='pending' else None)
    library.upsert(item)
    def fail(*a,**k):raise ProviderError('provider_unavailable','tmdb')
    runtime=Services(None,library.store,library,None,SimpleNamespace(candidates=fail),None,None)
    with pytest.raises(ProviderError):runtime.lookup({'item_id':item.id},context)
    latest=library.get(item.id)
    assert latest.status==('error' if status=='pending' else status)
    assert latest.decision==item.decision
    assert latest.metadata['lookup_state']=='error' and latest.metadata['lookup_error']=='provider_unavailable'

def test_lookup_failure_after_concurrent_confirmation_retains_approval(library,tmp_path,context):
    root=tmp_path/'incoming';root.mkdir();source=library.add_source(root)
    item=MediaItem(id='i',source_id=source['id'],path=str(root/'a.mkv'),kind='movies',signature={'size':1})
    library.upsert(item)
    def fail(*a,**k):
        library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'A'}))
        raise ProviderError('provider_unavailable','tmdb')
    runtime=Services(None,library.store,library,None,SimpleNamespace(candidates=fail),None,None)
    with pytest.raises(ProviderError):runtime.lookup({'item_id':item.id},context)
    assert library.get(item.id).status=='approved'
