import ntpath
import os
import posixpath
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from orion.app import create_app
from orion.discovery import Discovery
from orion.executor import Executor
from orion.models import MatchDecision
from orion.planner import Planner, PlanOptions
from orion.store import item_id
from tests_support import make_plan


def directory_plan(library, tmp_path, context, kind='movies', companion_name='movie.en.HI.srt'):
    incoming = tmp_path / 'incoming'
    folder = incoming / 'Original'
    nested = folder / 'Old season'
    nested.mkdir(parents=True)
    media = nested / ('Movie.MKV' if kind == 'movies' else 'Movie.S01E02.MKV')
    media.write_bytes(b'video bytes')
    companion = nested / companion_name
    companion.write_bytes(b'subtitle bytes')
    sid = library.add_source(incoming, kind=kind)['id']
    Discovery(library).scan([sid], False, context)
    item = library.query().items[0]
    library.decide(item.id, MatchDecision(item_id=item.id, metadata={'title': 'Film', 'year': '2020'}))
    destination = tmp_path / 'library'
    destination.mkdir()
    did = item_id('destination', destination)
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)', (did, str(destination), 'Library'))
    return Planner(library), item.id, media, companion, did


@pytest.mark.parametrize('normalize,companion_name,associated', [
    (ntpath.normcase, 'movie.en.HI.srt', True),
    (posixpath.normcase, 'movie.en.HI.srt', False),
    (posixpath.normcase, 'Movie.en.HI.srt', True),
])
def test_directory_companion_uses_host_case_rules(library, tmp_path, context, monkeypatch, normalize, companion_name, associated):
    planner, iid, media, companion, _ = directory_plan(library, tmp_path, context, companion_name=companion_name)
    monkeypatch.setattr('orion.planner.os.path.normcase', normalize)
    pairs, _ = planner._layout(library.get(iid), PlanOptions(), tmp_path / 'library', set())
    target = next(dst for src, dst, _ in pairs if src == companion)
    assert target.name == ('Film (2020).en.HI.srt' if associated else 'movie.en.HI.srt')


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows directory companion move and undo')
@pytest.mark.parametrize('kind,companion_name,want_relative', [
    ('movies', 'movie.en.HI.srt', 'Old season/Film (2020).en.HI.srt'),
    ('series', 'movie.s01e02.en.HI.srt', 'Season 01/Film - S01E02.en.HI.srt'),
])
def test_windows_directory_companion_moves_with_video_and_undo(library, tmp_path, context, kind, companion_name, want_relative):
    planner, iid, media, companion, did = directory_plan(library, tmp_path, context, kind, companion_name)
    plan = planner.create([iid], PlanOptions(destination_id=did))
    assert not plan.issues
    targets = {Path(op.source): Path(op.destination) for op in plan.operations}
    folder = Path(plan.operations[0].verification['destination_item_path'])
    assert targets[companion] == folder / want_relative
    assert targets[companion].parent == targets[media].parent
    executor = Executor(library, planner)
    result = executor.execute(plan.id, plan.revision, context)
    assert result.state == 'completed'
    assert not media.exists() and not companion.exists()
    assert targets[media].read_bytes() == b'video bytes'
    assert targets[companion].read_bytes() == b'subtitle bytes'
    undo = executor.undo_plan(result.batch_id)
    assert not undo.issues
    assert executor.execute(undo.id, undo.revision, context).state == 'completed'
    assert media.read_bytes() == b'video bytes'
    assert companion.read_bytes() == b'subtitle bytes'
    assert not folder.exists()


def test_category_api_exposes_and_updates_only_authoritative_migrated_row(legacy, context):
    with sqlite3.connect(legacy) as conn:
        conn.execute("UPDATE categories SET name='Cinema' WHERE name='Movies'")
    with TestClient(create_app(legacy.parent), base_url='http://127.0.0.1:4321') as client:
        client.headers['X-Orion-CSRF'] = client.get('/api/v1/session').json()['csrf_token']
        categories = client.get('/api/v1/categories').json()
        movies = [row for row in categories if row['kind'] == 'movies']
        assert len(movies) == 1 and movies[0]['name'] == 'Cinema'
        authoritative = movies[0]
        hidden = client.put('/api/v1/categories/movies', json={'dest_subpath': 'Ignored', 'api_pref': 'tmdb'})
        assert hidden.status_code == 404
        update = client.put('/api/v1/categories/' + authoritative['id'], json={'dest_subpath': 'New Cinema', 'api_pref': 'tmdb'})
        assert update.status_code == 200
        runtime = client.app.state.services
        source_root = legacy.parent / 'a'
        source_root.mkdir()
        source = source_root / 'new.mkv'
        source.write_bytes(b'media')
        destination = legacy.parent / 'library'
        destination.mkdir()
        with runtime.store.transaction() as conn:
            sid = conn.execute('SELECT id FROM orion_sources WHERE path=?', (str(source_root),)).fetchone()[0]
            did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
            assert conn.execute("SELECT dest_subpath FROM orion_categories WHERE id='movies'").fetchone()[0] == 'Movies'
        Discovery(runtime.library).scan([sid], False, context)
        item = next(row for row in runtime.library.query().items if row.path == str(source))
        runtime.library.decide(item.id, MatchDecision(item_id=item.id, metadata={'title': 'Arrival'}))
        plan = runtime.planner.create([item.id], PlanOptions(destination_id=did))
        assert not plan.issues
        assert Path(plan.operations[0].destination) == destination / 'New Cinema' / 'Arrival' / 'Arrival.mkv'
        assert runtime.providers.preferred_provider('movies') == 'tmdb'


@pytest.mark.parametrize('directory', [False, True])
@pytest.mark.parametrize('late', [False, True])
def test_stale_indexed_final_path_blocks_all_moves(library, tmp_path, context, directory, late):
    planner, original, source, target = make_plan(library, tmp_path, context, directory=directory)
    iid = original.operations[0].item_id
    final_item_path = original.operations[0].verification['destination_item_path']
    stale = library.get(iid).model_copy(update={'id': str(uuid4()), 'path': final_item_path, 'status': 'organised'})
    library.upsert(stale)
    assert not Path(final_item_path).exists()
    if late:
        plan = original
    else:
        with library.store.transaction() as conn:
            did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
        plan = planner.create([iid], PlanOptions(destination_id=did))
        assert any(issue.code == 'indexed_destination_exists' for issue in plan.issues)
    checked = planner.validate(plan.id, plan.revision)
    assert any(issue.code == 'indexed_destination_exists' for issue in checked.issues)
    with pytest.raises(ValueError, match='indexed_destination_exists'):
        Executor(library, planner).execute(plan.id, plan.revision, context)
    assert source.read_bytes() == b'original media bytes'
    assert not target.exists()
    if directory:
        assert (source.parent / 'original.en.srt').read_bytes() == b'subtitle'
    assert library.get(iid).path == original.operations[0].verification['item_path']
    assert library.get(stale.id).path == final_item_path
    with library.store.transaction() as conn:
        assert conn.execute('SELECT COUNT(*) FROM orion_batches').fetchone()[0] == 0


def test_hidden_seed_category_update_is_rejected_atomically(legacy):
    with sqlite3.connect(legacy) as conn:
        conn.execute("UPDATE categories SET name='Cinema' WHERE name='Movies'")
    with TestClient(create_app(legacy.parent), base_url='http://127.0.0.1:4321') as client:
        client.headers['X-Orion-CSRF'] = client.get('/api/v1/session').json()['csrf_token']
        result = client.put('/api/v1/categories/movies', json={'dest_subpath': 'Ignored', 'api_pref': 'tmdb'})
        assert result.status_code == 404
        with client.app.state.services.store.transaction() as conn:
            assert conn.execute("SELECT dest_subpath FROM orion_categories WHERE id='movies'").fetchone()[0] == 'Movies'
            assert conn.execute("SELECT dest_subpath FROM orion_categories WHERE name='Cinema'").fetchone()[0] == 'Films'
        assert client.app.state.services.config.get_pref('provider_movies') is None
