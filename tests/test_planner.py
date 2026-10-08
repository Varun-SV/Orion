import json
import os
import shutil
from pathlib import Path
import pytest
from orion.planner import Planner,PlanOptions
from orion.discovery import Discovery
from orion.models import MatchDecision
from orion.store import item_id

@pytest.fixture
def planned(library,tmp_path,context):
    source = tmp_path/'incoming'
    source.mkdir()
    file = source/'arrival-original.mkv'
    file.write_bytes(b'original media')
    sid = library.add_source(source,kind='movies')['id']
    Discovery(library).scan([sid],False,context)
    item = library.query().items[0]
    library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Arrival','year':'2016'}))
    dest = tmp_path/'library'
    dest.mkdir()
    did = item_id('destination',dest)
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)',(did,str(dest),'Library'))
    return library,Planner(library),item.id,file,did,dest

def test_preview_is_stored_and_read_only(planned):
    library,planner,iid,file,did,dest = planned
    before = file.read_bytes()
    plan = planner.create([iid],PlanOptions(destination_id=did))
    assert plan.issues == []
    assert plan.operations[0].destination == str(dest/'Movies'/'Arrival (2016)'/'Arrival (2016).mkv')
    assert file.read_bytes() == before
    assert list(dest.iterdir()) == []
    loaded = planner.get(plan.id)
    assert loaded == plan
    with pytest.raises(ValueError):
        planner.validate(plan.id,plan.revision+1)

def test_changed_source_invalidates_immutable_plan(planned):
    _,planner,iid,file,did,_ = planned
    plan = planner.create([iid],PlanOptions(destination_id=did))
    file.write_bytes(b'changed')
    checked = planner.validate(plan.id,plan.revision)
    assert 'source_changed' in [issue.code for issue in checked.issues]
    assert planner.get(plan.id).operations == plan.operations

def test_existing_destination_blocks_preview(planned):
    _,planner,iid,_,did,dest = planned
    target = dest/'Movies'/'Arrival (2016)'/'Arrival (2016).mkv'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'keep me')
    plan = planner.create([iid],PlanOptions(destination_id=did))
    assert plan.issues[0].code == 'destination_exists'
    assert target.read_bytes() == b'keep me'

def test_keep_both_generates_explicit_separate_name(planned):
    _,planner,iid,_,did,dest = planned
    target = dest/'Movies'/'Arrival (2016)'/'Arrival (2016).mkv'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'keep me')
    plan = planner.create([iid],PlanOptions(destination_id=did,conflict='keep_both'))
    assert not plan.issues
    assert Path(plan.operations[0].destination).name == 'Arrival (2016) (2).mkv'

def test_unavailable_destination_does_not_get_created(planned):
    _,planner,iid,_,did,dest = planned
    dest.rmdir()
    plan = planner.create([iid],PlanOptions(destination_id=did))
    assert 'destination_unavailable' in [issue.code for issue in plan.issues]
    assert not dest.exists()

def test_plan_cannot_target_an_unconfigured_root(planned):
    _,planner,iid,_,_,_ = planned
    with pytest.raises(ValueError):
        planner.create([iid],PlanOptions(destination_id='not-configured'))

def test_inplace_music_needs_no_destination(library,tmp_path,context):
    root = tmp_path/'songs'
    root.mkdir()
    file = root/'track.flac'
    file.write_bytes(b'fixture')
    sid = library.add_source(root,kind='music')['id']
    Discovery(library).scan([sid],False,context)
    item = library.query().items[0]
    library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Song','artist':'Artist','album':'Album'}))
    plan = Planner(library).create([item.id],PlanOptions(in_place=True))
    assert plan.issues == []
    assert plan.operations[0].destination == str(root/'Song.flac')

def test_directory_manifest_preserves_associated_files(library,tmp_path,context):
    root = tmp_path/'incoming'
    movie = root/'wrong-name'
    movie.mkdir(parents=True)
    (movie/'video.mkv').write_bytes(b'film')
    (movie/'video.en.srt').write_text('subtitle')
    (movie/'poster.jpg').write_bytes(b'art')
    sid = library.add_source(root,kind='movies')['id']
    Discovery(library).scan([sid],False,context)
    item = library.query().items[0]
    library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Arrival','year':'2016'}))
    dest = tmp_path/'library'
    dest.mkdir()
    did = item_id('destination',dest)
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)',(did,str(dest),'Library'))
    plan = Planner(library).create([item.id],PlanOptions(destination_id=did))
    assert len(plan.operations) == 3
    assert {Path(op.destination).name for op in plan.operations} == {'Arrival (2016).mkv','Arrival (2016).en.srt','poster.jpg'}

def test_same_volume_rename_does_not_require_duplicate_space(planned,monkeypatch):
    _,planner,iid,_,did,_ = planned
    monkeypatch.setattr(shutil,'disk_usage',lambda p:shutil._ntuple_diskusage(100,100,0))
    assert planner.create([iid],PlanOptions(destination_id=did)).issues == []

def test_decision_change_requires_new_preview(planned):
    library,planner,iid,_,did,_ = planned
    plan = planner.create([iid],PlanOptions(destination_id=did))
    library.decide(iid,MatchDecision(item_id=iid,metadata={'title':'A different film'}))
    assert 'decision_changed' in [i.code for i in planner.validate(plan.id,plan.revision).issues]

def test_cross_volume_space_is_checked_before_execution(planned,monkeypatch):
    _,planner,iid,_,did,dest = planned
    original = Path.stat
    def other_volume(path,*a,**kw):
        result = original(path,*a,**kw)
        if path == dest:
            values = list(result)
            values[2] = result.st_dev + 1
            return os.stat_result(values)
        return result
    monkeypatch.setattr(Path,'stat',other_volume)
    monkeypatch.setattr(shutil,'disk_usage',lambda p:shutil._ntuple_diskusage(100,100,0))
    assert 'insufficient_space' in [i.code for i in planner.create([iid],PlanOptions(destination_id=did)).issues]

def test_destination_permissions_block_preflight(planned,monkeypatch):
    _,planner,iid,_,did,_ = planned
    monkeypatch.setattr(os,'access',lambda *a:False)
    assert 'destination_access' in [i.code for i in planner.create([iid],PlanOptions(destination_id=did)).issues]

def test_case_collision_keeps_existing_file(planned):
    if os.name != 'nt':
        pytest.skip('Case-insensitive host filesystem regression')
    _,planner,iid,_,did,dest = planned
    target = dest/'MOVIES'/'ARRIVAL (2016)'/'ARRIVAL (2016).MKV'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'other edition')
    plan = planner.create([iid],PlanOptions(destination_id=did))
    assert 'destination_exists' in [i.code for i in plan.issues]
    assert target.read_bytes() == b'other edition'

def test_series_directory_keeps_episode_and_artwork_together(library,tmp_path,context):
    root = tmp_path/'shows'
    show = root/'Original show'
    show.mkdir(parents=True)
    (show/'Original.Show.S01E02.mkv').write_bytes(b'episode')
    (show/'poster.jpg').write_bytes(b'poster')
    sid = library.add_source(root,kind='series')['id']
    Discovery(library).scan([sid],False,context)
    item = library.query().items[0]
    library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Show','year':'2020'}))
    dest = tmp_path/'library'
    dest.mkdir()
    did = item_id('destination',dest)
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)',(did,str(dest),'Library'))
    plan = Planner(library).create([item.id],PlanOptions(destination_id=did))
    assert not plan.issues
    assert all(str(dest/'Series'/'Show (2020)') in op.destination for op in plan.operations)
