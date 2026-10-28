import xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from tests_support import make_plan, Crash
from orion.executor import Executor
from orion.planner import PlanOptions
from orion.naming import NamingProfile
from orion.models import MatchDecision


def enabled_plan(library, tmp_path, context, **flags):
    planner, original, source, target = make_plan(library, tmp_path, context)
    item = library.get(original.operations[0].item_id)
    library.decide(item.id, MatchDecision(item_id=item.id, provider='tmdb', provider_id='329865',
        metadata={'title': 'A & B', 'year': '2016', 'plot': '<home> & away'}))
    with library.store.transaction() as conn:
        did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan = planner.create([item.id], PlanOptions(destination_id=did,
        profile=NamingProfile(nfo_enabled=True, **flags)))
    return planner, plan, source


def test_sidecar_defaults_off():
    p = NamingProfile()
    assert not p.nfo_enabled and not p.artwork_enabled and not p.episode_nfo_enabled


def test_nfo_is_previewed_escaped_and_removed_by_guarded_undo(library, tmp_path, context):
    planner, plan, source = enabled_plan(library, tmp_path, context)
    assert not plan.issues
    output = next(op for op in plan.operations if op.kind == 'create_nfo')
    assert not Path(output.destination).exists()
    executor = Executor(library, planner)
    result = executor.execute(plan.id, 1, context)
    assert result.state == 'completed'
    parsed = ET.parse(output.destination).getroot()
    assert parsed.findtext('title') == 'A & B'
    assert parsed.findtext('plot') == '<home> & away'
    assert parsed.find('uniqueid').attrib['type'] == 'tmdb'
    undo = executor.undo_plan(result.batch_id)
    assert not undo.issues
    restored = executor.execute(undo.id, 1, context)
    assert restored.state == 'completed'
    assert restored.created_sidecars_removed == [output.destination]
    assert source.read_bytes() == b'original media bytes'
    assert not Path(output.destination).exists()


def test_changed_generated_nfo_survives_without_blocking_media_undo(library, tmp_path, context):
    planner, plan, source = enabled_plan(library, tmp_path, context)
    executor = Executor(library, planner)
    result = executor.execute(plan.id, 1, context)
    output = next(op for op in plan.operations if op.kind == 'create_nfo')
    Path(output.destination).write_bytes(b'user edit')
    undo = executor.undo_plan(result.batch_id)
    assert not undo.issues
    assert any(w.code == 'sidecar_changed' for w in undo.warnings)
    assert executor.execute(undo.id, 1, context).state == 'completed'
    assert source.exists()
    assert Path(output.destination).read_bytes() == b'user edit'


def test_existing_nfo_is_preserved_with_warning(library, tmp_path, context):
    planner, plan, source = enabled_plan(library, tmp_path, context)
    output = next(op for op in plan.operations if op.kind == 'create_nfo')
    Path(output.destination).parent.mkdir(parents=True)
    Path(output.destination).write_bytes(b'user metadata')
    with library.store.transaction() as conn:
        did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    fresh = planner.create([output.item_id], PlanOptions(destination_id=did, profile=NamingProfile(nfo_enabled=True)))
    assert not fresh.issues
    assert not any(op.kind == 'create_nfo' for op in fresh.operations)
    assert any(w.code == 'sidecar_exists' for w in fresh.warnings)
    assert Executor(library, planner).execute(fresh.id, 1, context).state == 'completed'
    assert Path(output.destination).read_bytes() == b'user metadata'


def test_generated_publication_recovers_without_deleting_media(library, tmp_path, context):
    planner, plan, source = enabled_plan(library, tmp_path, context)
    class AtPublish(Executor):
        def _journal(self, op, state, **details):
            super()._journal(op, state, **details)
            if op.kind == 'create_nfo' and state == 'finalised':
                raise Crash()
    with pytest.raises(Crash):
        AtPublish(library, planner).execute(plan.id, 1, context)
    executor = Executor(library, planner)
    assert executor.execute(plan.id, 1, context).state == 'completed'
    assert all(Path(op.destination).exists() for op in plan.operations)


def test_artwork_failure_preserves_successful_media_and_is_retryable(library, tmp_path, context, monkeypatch):
    from orion.integrations.sidecars import Sidecars
    planner, original, source, target = make_plan(library, tmp_path, context)
    item = library.get(original.operations[0].item_id)
    library.decide(item.id, MatchDecision(item_id=item.id, metadata={'title':'Arrival',
        'artwork_url':'https://image.tmdb.org/t/p/w500/test.jpg'}))
    with library.store.transaction() as conn:
        did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan = planner.create([item.id], PlanOptions(destination_id=did, profile=NamingProfile(artwork_enabled=True)))
    monkeypatch.setattr(Sidecars, 'artwork', staticmethod(lambda *a: (_ for _ in ()).throw(OSError('offline'))))
    executor = Executor(library, planner)
    assert executor.execute(plan.id, 1, context).state == 'partial'
    moved = next(op for op in plan.operations if op.kind == 'move')
    assert library.get(item.id).path == moved.destination
    assert library.get(item.id).status == 'organised'
    monkeypatch.setattr(Sidecars, 'artwork', staticmethod(lambda *a: b'fixture image'))
    assert executor.execute(plan.id, 1, context).state == 'completed'


def test_loose_subtitle_and_existing_nfo_move_with_media(library, tmp_path, context):
    planner, original, source, target = make_plan(library, tmp_path, context)
    source.with_suffix('.en.srt').write_bytes(b'subtitle')
    source.with_suffix('.nfo').write_bytes(b'user nfo')
    with library.store.transaction() as conn:
        did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    fresh = planner.create([original.operations[0].item_id], PlanOptions(destination_id=did))
    assert len(fresh.operations) == 3
    executor = Executor(library, planner)
    result = executor.execute(fresh.id, 1, context)
    assert result.state == 'completed'
    assert executor.execute(executor.undo_plan(result.batch_id).id, 1, context).state == 'completed'
    assert source.with_suffix('.nfo').read_bytes() == b'user nfo'
    assert source.with_suffix('.en.srt').read_bytes() == b'subtitle'
def test_series_root_and_episode_metadata_use_one_cached_season(library,tmp_path,context):
    from orion.discovery import Discovery
    from orion.planner import Planner
    from orion.store import item_id
    root=tmp_path/'incoming';root.mkdir();show=root/'Original';show.mkdir()
    (show/'Show.S01E01.mkv').write_bytes(b'one');(show/'Show.S01E02.mkv').write_bytes(b'two')
    sid=library.add_source(root,kind='series')['id'];Discovery(library).scan([sid],False,context)
    item=library.query().items[0]
    library.decide(item.id,MatchDecision(item_id=item.id,provider='tmdb',provider_id='123',metadata={'title':'Show','year':'2020','plot':'Series plot'}))
    destination=tmp_path/'dest';destination.mkdir();did=item_id('destination',destination)
    with library.store.transaction() as conn:conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)',(did,str(destination),'Dest'))
    class Catalogue:
        calls=[]
        def get_cached(self,path):
            self.calls.append(path)
            return {'episodes':[{'episode_number':n,'name':f'Episode title {n}','overview':f'Plot {n}','air_date':'2020-01-01','id':100+n} for n in (1,2)]},True,'now'
    planner=Planner(library);planner.catalogue=Catalogue()
    plan=planner.create([item.id],PlanOptions(destination_id=did,profile=NamingProfile(nfo_enabled=True,episode_nfo_enabled=True)))
    assert not plan.issues
    assert planner.catalogue.calls==['tv/123/season/1']
    result=Executor(library,planner).execute(plan.id,1,context)
    assert result.state=='completed'
    assert Path(library.get(item.id).path)==destination/'Series'/'Show (2020)'
    episodes=[op for op in plan.operations if op.kind=='create_nfo' and 'Season' in op.destination]
    assert len(episodes)==2
    parsed=ET.parse(episodes[0].destination).getroot()
    assert parsed.findtext('title')=='Episode title 1'
    assert parsed.findtext('uniqueid')=='101'
    assert parsed.findtext('showtitle')=='Show'


def test_music_album_artist_and_tag_only_cover_warning():
    from orion.models import MediaItem
    from orion.integrations.sidecars import Sidecars
    item=MediaItem(id='a',source_id='s',path='a.flac',kind='music',signature={'type':'file'},decision=MatchDecision(item_id='a',metadata={'title':'Track','artist':'A & B','album':'Album','year':'2020'}))
    specs=Sidecars.plan(item,NamingProfile(nfo_enabled=True,artwork_enabled=True))
    assert {Path(spec.path).name for spec in specs if spec.path}=={'artist.nfo','album.nfo'}
    assert any('release_id_unavailable' in spec.warning for spec in specs)
    artist=next(spec for spec in specs if spec.path.endswith('artist.nfo'))
    assert ET.fromstring(artist.content).findtext('title')=='A & B'


def test_book_has_cover_projection_and_no_unsupported_nfo():
    from orion.models import MediaItem
    from orion.integrations.sidecars import Sidecars
    item=MediaItem(id='a',source_id='s',path='a.epub',kind='books',signature={'type':'file'},decision=MatchDecision(item_id='a',metadata={'title':'Book','author':'Author','poster_url':'https://covers.openlibrary.org/b/id/1-M.jpg'}))
    specs=Sidecars.plan(item,NamingProfile(nfo_enabled=True,artwork_enabled=True))
    assert len(specs)==1 and specs[0].kind=='create_artwork'
    assert Path(specs[0].path)==Path('Author/Book.jpg')


@pytest.mark.parametrize('url',['http://image.tmdb.org/a.jpg','https://localhost/a.jpg','https://image.tmdb.org@evil.example/a.jpg','https://image.tmdb.org/a.jpg?token=secret','https://image.tmdb.org:123/a.jpg'])
def test_artwork_rejects_untrusted_or_credentialed_origin(url):
    from orion.integrations.sidecars import Sidecars
    with pytest.raises(ValueError):Sidecars.valid_artwork_url(url)


def test_download_decodes_png_to_real_jpeg_with_no_secret_headers(context,monkeypatch):
    import io
    from PIL import Image
    from orion.integrations.sidecars import Sidecars
    image=io.BytesIO();Image.new('RGB',(3,2),'red').save(image,format='PNG')
    class Response:
        status_code=200;headers={}
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def iter_content(self,*a):yield image.getvalue()
    class Session:
        headers={};trust_env=True
        def get(self,url,**kwargs):
            assert kwargs['allow_redirects'] is False
            assert not any('token' in key.lower() or 'authorization' in key.lower() for key in self.headers)
            return Response()
        def close(self):pass
    monkeypatch.setattr('orion.integrations.sidecars.requests.Session',Session)
    data=Sidecars.artwork('https://image.tmdb.org/test.png',context)
    assert Image.open(io.BytesIO(data)).format=='JPEG'


def test_sidecar_race_never_overwrites_and_keeps_moved_media(library,tmp_path,context):
    from orion.filesystem import Filesystem
    planner,plan,source=enabled_plan(library,tmp_path,context)
    class Race(Filesystem):
        def rename_noreplace(self,src,dst):
            if str(src).endswith('.part'):Path(dst).write_bytes(b'user won race')
            super().rename_noreplace(src,dst)
    result=Executor(library,planner,filesystem=Race()).execute(plan.id,1,context)
    assert result.state=='partial'
    output=next(op for op in plan.operations if op.kind=='create_nfo')
    assert Path(output.destination).read_bytes()==b'user won race'
    assert library.get(output.item_id).status=='organised'


def test_unowned_output_temporary_file_survives(library,tmp_path,context):
    planner,plan,source=enabled_plan(library,tmp_path,context)
    output=next(op for op in plan.operations if op.kind=='create_nfo')
    target=Path(output.destination);target.parent.mkdir(parents=True)
    temp=target.parent/('.orion-'+output.id+'.part');temp.write_bytes(b'unowned')
    result=Executor(library,planner).execute(plan.id,1,context)
    assert result.state=='partial' and temp.read_bytes()==b'unowned'


def test_saved_collection_sidecar_defaults_apply_without_explicit_profile(library,tmp_path,context):
    from orion.profiles import Profiles
    planner,plan,source,target=make_plan(library,tmp_path,context)
    profiles=Profiles(library);profile=profiles.get('default-movies')
    profiles.save(profile.model_copy(update={'nfo_enabled':True}))
    with library.store.transaction() as conn:did=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    fresh=planner.create([plan.operations[0].item_id],PlanOptions(destination_id=did))
    assert any(op.kind=='create_nfo' for op in fresh.operations)


def test_video_inplace_is_rejected_without_operations(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    fresh=planner.create([plan.operations[0].item_id],PlanOptions(in_place=True))
    assert not fresh.operations and any(issue.code=='invalid_layout' for issue in fresh.issues)
