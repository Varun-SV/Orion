import ntpath
import os
import posixpath
from pathlib import Path

import pytest

from orion.config import Config
from orion.discovery import Discovery
from orion.executor import Executor
from orion.models import MatchDecision
from orion.planner import Planner, PlanOptions
from orion.store import item_id
from test_api import client


def movie_with_companion(library, tmp_path, context, media_name, companion_name):
    incoming = tmp_path / 'incoming'
    incoming.mkdir()
    media = incoming / media_name
    media.write_bytes(b'movie bytes')
    companion = incoming / companion_name
    companion.write_bytes(b'subtitle bytes')
    source_id = library.add_source(incoming, kind='movies')['id']
    Discovery(library).scan([source_id], False, context)
    item = library.query().items[0]
    library.decide(item.id, MatchDecision(item_id=item.id, metadata={'title':'Film', 'year':'2020'}))
    destination = tmp_path / 'library'
    destination.mkdir()
    destination_id = item_id('destination', destination)
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)', (destination_id, str(destination), 'Library'))
    return Planner(library), item.id, media, companion, destination_id


@pytest.mark.parametrize('media_name,companion_name', [
    ('Movie.MKV', 'Movie.en.HI.srt'),
    pytest.param('Movie.MKV', 'movie.en.HI.srt', marks=pytest.mark.skipif(os.name != 'nt', reason='Windows host case normalization')),
])
def test_loose_movie_and_language_companion_move_and_undo(library, tmp_path, context, media_name, companion_name):
    planner, item_id, media, companion, destination_id = movie_with_companion(library, tmp_path, context, media_name, companion_name)
    plan = planner.create([item_id], PlanOptions(destination_id=destination_id))
    assert not plan.issues
    assert len(plan.operations) == 2
    targets = {Path(op.source):Path(op.destination) for op in plan.operations}
    assert targets[companion].name == 'Film (2020).en.HI.srt'
    executor = Executor(library, planner)
    moved = executor.execute(plan.id, plan.revision, context)
    assert moved.state == 'completed'
    assert not media.exists() and not companion.exists()
    assert targets[media].read_bytes() == b'movie bytes'
    assert targets[companion].read_bytes() == b'subtitle bytes'
    undo = executor.undo_plan(moved.batch_id)
    assert not undo.issues and len(undo.operations) == 2
    assert executor.execute(undo.id, undo.revision, context).state == 'completed'
    assert media.read_bytes() == b'movie bytes' and companion.read_bytes() == b'subtitle bytes'
    assert all(not target.exists() for target in targets.values())


@pytest.mark.parametrize('normalize,media_name,companion_name,included', [
    (ntpath.normcase, 'Movie.MKV', 'movie.en.HI.srt', True),
    (posixpath.normcase, 'Movie.MKV', 'movie.en.HI.srt', False),
    (posixpath.normcase, 'Movie.MKV', 'Movie.en.HI.srt', True),
    (ntpath.normcase, 'Straße.MKV', 'straße.de.HI.srt', True),
    (ntpath.normcase, 'Straße.MKV', 'STRASSE.de.HI.srt', False),
])
def test_companion_matching_uses_host_case_rules_and_preserves_suffix(library, tmp_path, context, monkeypatch, normalize, media_name, companion_name, included):
    planner, item_id, media, companion, _ = movie_with_companion(library, tmp_path, context, media_name, companion_name)
    # Exercise both host rules without replacing pathlib's concrete host type.
    monkeypatch.setattr('orion.planner.os.path.normcase', normalize)
    pairs, _ = planner._layout(library.get(item_id), PlanOptions(), tmp_path / 'library', set())
    assert (companion in [source for source, _, _ in pairs]) is included
    if included:
        destination = next(target for source, target, _ in pairs if source == companion)
        assert destination.name == 'Film (2020)' + companion.name[len(media.stem):]


def add_destination(client, root):
    root.mkdir()
    response = client.post('/api/v1/destinations', json={'path':str(root)})
    assert response.status_code == 201
    return response.json()['id']


def set_default(client, destination_id):
    response = client.put('/api/v1/settings', json={'default_destination':destination_id})
    assert response.status_code == 200
    assert response.json()['default_destination'] == destination_id


def test_removing_default_destination_clears_api_and_persisted_preference(client, tmp_path):
    destination_id = add_destination(client, tmp_path / 'default-library')
    set_default(client, destination_id)
    assert client.delete('/api/v1/destinations/' + destination_id).json() == {'removed':True}
    assert client.get('/api/v1/destinations').json() == []
    assert client.get('/api/v1/settings').json()['default_destination'] is None
    assert Config(tmp_path).get_pref('default_destination') is None


def test_removing_another_destination_preserves_default(client, tmp_path):
    default_id = add_destination(client, tmp_path / 'default-library')
    another_id = add_destination(client, tmp_path / 'another-library')
    set_default(client, default_id)
    assert client.delete('/api/v1/destinations/' + another_id).status_code == 200
    assert client.get('/api/v1/settings').json()['default_destination'] == default_id
    assert Config(tmp_path).get_pref('default_destination') == default_id


def test_recovery_history_rejection_preserves_default_and_destination(client, tmp_path, context):
    runtime = client.app.state.services
    planner, item_id, _, _, destination_id = movie_with_companion(runtime.library, tmp_path, context, 'Movie.MKV', 'Movie.en.srt')
    plan = planner.create([item_id], PlanOptions(destination_id=destination_id))
    assert not plan.issues
    set_default(client, destination_id)
    response = client.delete('/api/v1/destinations/' + destination_id)
    assert response.status_code == 400 and 'recovery history' in response.json()['message']
    assert client.get('/api/v1/settings').json()['default_destination'] == destination_id
    assert client.get('/api/v1/destinations').json()[0]['id'] == destination_id
    assert Config(tmp_path).get_pref('default_destination') == destination_id


def test_missing_destination_rejection_preserves_default(client, tmp_path):
    destination_id = add_destination(client, tmp_path / 'default-library')
    set_default(client, destination_id)
    assert client.delete('/api/v1/destinations/missing').status_code == 404
    assert client.get('/api/v1/settings').json()['default_destination'] == destination_id