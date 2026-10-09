import os
from pathlib import Path
import pytest
from tests_support import make_plan, Crash
from orion.discovery import Discovery
from orion.executor import Executor
from orion.filesystem import Filesystem
from orion.integrations.sidecars import Sidecars
from orion.models import MatchDecision
from orion.naming import NamingProfile
from orion.planner import Planner, PlanOptions


def case_plan(library, tmp_path, context, kind='music', conflict='block'):
    root = tmp_path / 'incoming'
    root.mkdir()
    suffix = '.flac' if kind == 'music' else '.epub'
    source = root / ('track' + suffix)
    source.write_bytes(b'case preserving media')
    sid = library.add_source(root, kind=kind)['id']
    Discovery(library).scan([sid], False, context)
    item = library.query().items[0]
    library.decide(item.id, MatchDecision(item_id=item.id, metadata={'title': 'Track', 'filename': 'Track' + suffix}))
    planner = Planner(library)
    plan = planner.create([item.id], PlanOptions(in_place=True, conflict=conflict))
    return planner, plan, source, root / ('Track' + suffix)


def test_imported_category_subpath_is_authoritative_after_migration(legacy, context):
    from orion.store import Store
    from orion.library import Library
    import sqlite3
    with sqlite3.connect(legacy) as conn:
        conn.execute("UPDATE categories SET name='Cinema' WHERE name='Movies'")
    store = Store(legacy)
    store.migrate()
    library = Library(store)
    root = legacy.parent / 'a'
    root.mkdir()
    source = root / 'new.mkv'
    source.write_bytes(b'media')
    with store.transaction() as conn:
        sid = conn.execute('SELECT id FROM orion_sources WHERE path=?', (str(root),)).fetchone()[0]
        destination = legacy.parent / 'library'
        destination.mkdir()
        did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    Discovery(library).scan([sid], False, context)
    item = next(item for item in library.query().items if item.path == str(source))
    library.decide(item.id, MatchDecision(item_id=item.id, metadata={'title': 'Arrival'}))
    planner = Planner(library)
    for subpath in ['Films', 'Cinema']:
        with store.transaction() as conn:
            conn.execute("UPDATE orion_categories SET dest_subpath=? WHERE kind='movies' AND id!='movies'", (subpath,))
        plan = planner.create([item.id], PlanOptions(destination_id=did))
        assert not plan.issues
        assert Path(plan.operations[0].destination) == destination / subpath / 'Arrival' / 'Arrival.mkv'


@pytest.mark.parametrize('kind', ['music', 'books'])
@pytest.mark.parametrize('conflict', ['block', 'skip', 'keep_both'])
def test_case_only_inplace_rename_preserves_spelling_bytes_and_undo(library, tmp_path, context, kind, conflict):
    planner, plan, source, target = case_plan(library, tmp_path, context, kind, conflict)
    assert len(plan.operations) == 1
    assert not plan.issues
    executor = Executor(library, planner)
    result = executor.execute(plan.id, 1, context)
    assert result.state == 'completed'
    assert target.read_bytes() == b'case preserving media'
    if os.name == 'nt':
        assert source.exists()  # The old spelling aliases the new name; never unlink it.
    else:
        assert not source.exists()
    assert target.name in [p.name for p in target.parent.iterdir()]
    assert source.name not in [p.name for p in source.parent.iterdir()]
    assert library.get(plan.operations[0].item_id).path == str(target)
    undo = executor.undo_plan(result.batch_id)
    assert not undo.issues
    assert executor.execute(undo.id, 1, context).state == 'completed'
    assert source.read_bytes() == b'case preserving media'
    assert source.name in [p.name for p in source.parent.iterdir()]
    assert target.name not in [p.name for p in target.parent.iterdir()]


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows case-insensitive publication')
@pytest.mark.parametrize('leg', [1, 2])
def test_case_rename_recovers_crash_after_each_publication_leg(library, tmp_path, context, leg):
    planner, plan, source, target = case_plan(library, tmp_path, context)
    assert len(plan.operations) == 1
    assert not plan.issues
    class CrashAfterLeg(Filesystem):
        calls = 0
        def rename_noreplace(self, src, dst):
            super().rename_noreplace(src, dst)
            self.calls += 1
            if self.calls == leg:
                raise Crash()
    with pytest.raises(Crash):
        Executor(library, planner, filesystem=CrashAfterLeg()).execute(plan.id, 1, context)
    executor = Executor(library, planner)
    assert executor.execute(plan.id, 1, context).state == 'completed'
    assert target.read_bytes() == b'case preserving media'
    assert [p.name for p in target.parent.iterdir()] == ['Track.flac']


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows case-insensitive publication')
def test_case_rename_racing_new_destination_is_preserved(library, tmp_path, context):
    planner, plan, source, target = case_plan(library, tmp_path, context)
    assert len(plan.operations) == 1
    class Race(Filesystem):
        def rename_noreplace(self, src, dst):
            if str(src).endswith('.part'):
                Path(dst).write_bytes(b'new arrival')
            super().rename_noreplace(src, dst)
    executor = Executor(library, planner, filesystem=Race())
    assert executor.execute(plan.id, 1, context).state == 'failed'
    assert target.read_bytes() == b'new arrival'
    assert (source.parent / ('.orion-' + plan.operations[0].id + '.part')).read_bytes() == b'case preserving media'
    with pytest.raises(ValueError):
        Executor(library, planner).execute(plan.id, 1, context)
    assert target.read_bytes() == b'new arrival'


@pytest.mark.parametrize('directory', [False, True])
def test_sidecar_retry_uses_verified_destinations_after_source_disconnect(library, tmp_path, context, monkeypatch, directory):
    planner, original, source, target = make_plan(library, tmp_path, context, directory=directory)
    iid = original.operations[0].item_id
    library.decide(iid, MatchDecision(item_id=iid, metadata={'title': 'Arrival', 'artwork_url': 'https://image.tmdb.org/test.jpg'}))
    with library.store.transaction() as conn:
        did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan = planner.create([iid], PlanOptions(destination_id=did, profile=NamingProfile(artwork_enabled=True)))
    monkeypatch.setattr(Sidecars, 'artwork', staticmethod(lambda *args: (_ for _ in ()).throw(OSError('offline'))))
    executor = Executor(library, planner)
    assert executor.execute(plan.id, 1, context).state == 'partial'
    source_root = tmp_path / 'incoming'
    source_root.rmdir()
    monkeypatch.setattr(Sidecars, 'artwork', staticmethod(lambda *args: b'fixture art'))
    assert executor.execute(plan.id, 1, context).state == 'completed'
    output = next(op for op in plan.operations if op.kind == 'create_artwork')
    assert Path(output.destination).read_bytes() == b'fixture art'
    assert library.get(iid).status == 'organised'


@pytest.mark.skipif(os.name == 'nt', reason='POSIX distinct case-sensitive entries')
def test_posix_case_only_destination_collision_preserves_both_files(library, tmp_path, context):
    planner, original, source, target = case_plan(library, tmp_path, context)
    target.write_bytes(b'existing distinct entry')
    item_id = original.operations[0].item_id
    plan = planner.create([item_id], PlanOptions(in_place=True))
    assert any(issue.code == 'destination_exists' for issue in plan.issues)
    assert source.read_bytes() == b'case preserving media'
    assert target.read_bytes() == b'existing distinct entry'


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows case-insensitive publication')
@pytest.mark.parametrize('boundary', ['intent', 'staged', 'finalised', 'completed'])
def test_case_rename_journal_boundaries_recover_original_bytes(library, tmp_path, context, boundary):
    planner, plan, source, target = case_plan(library, tmp_path, context)
    class CrashAtJournal(Executor):
        def _journal(self, op, state, **details):
            super()._journal(op, state, **details)
            if state == boundary:
                raise Crash()
    with pytest.raises(Crash):
        CrashAtJournal(library, planner).execute(plan.id, 1, context)
    executor = Executor(library, planner)
    assert not executor.reconcile(plan.id).review_operation_ids
    assert executor.execute(plan.id, 1, context).state == 'completed'
    assert source.exists() and target.exists()
    assert [p.name for p in target.parent.iterdir()] == ['Track.flac']
    assert target.read_bytes() == b'case preserving media'


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows case-insensitive publication')
def test_case_rename_unowned_staging_file_is_never_overwritten(library, tmp_path, context):
    planner, plan, source, target = case_plan(library, tmp_path, context)
    temp = source.parent / ('.orion-' + plan.operations[0].id + '.part')
    temp.write_bytes(b'unowned staging file')
    assert Executor(library, planner).execute(plan.id, 1, context).state == 'failed'
    assert temp.read_bytes() == b'unowned staging file'
    assert source.read_bytes() == b'case preserving media'
    assert target.name not in [p.name for p in target.parent.iterdir()]


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows case-insensitive publication')
def test_case_rename_changed_staging_file_is_retained_for_review(library, tmp_path, context):
    planner, plan, source, target = case_plan(library, tmp_path, context)
    class CrashAtStaging(Executor):
        def _journal(self, op, state, **details):
            super()._journal(op, state, **details)
            if state == 'staged':
                raise Crash()
    with pytest.raises(Crash):
        CrashAtStaging(library, planner).execute(plan.id, 1, context)
    temp = source.parent / ('.orion-' + plan.operations[0].id + '.part')
    temp.write_bytes(b'edited staged media')
    executor = Executor(library, planner)
    report = executor.reconcile(plan.id)
    assert report.review_operation_ids == [plan.operations[0].id]
    with pytest.raises(ValueError):
        executor.execute(plan.id, 1, context)
    assert temp.read_bytes() == b'edited staged media'
    assert not target.exists()


def test_disconnected_sidecar_retry_rejects_changed_completed_media(library, tmp_path, context, monkeypatch):
    planner, original, source, target = make_plan(library, tmp_path, context)
    iid = original.operations[0].item_id
    library.decide(iid, MatchDecision(item_id=iid, metadata={'title': 'Arrival', 'artwork_url': 'https://image.tmdb.org/test.jpg'}))
    with library.store.transaction() as conn:
        did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan = planner.create([iid], PlanOptions(destination_id=did, profile=NamingProfile(artwork_enabled=True)))
    monkeypatch.setattr(Sidecars, 'artwork', staticmethod(lambda *args: (_ for _ in ()).throw(OSError('offline'))))
    executor = Executor(library, planner)
    assert executor.execute(plan.id, 1, context).state == 'partial'
    (tmp_path / 'incoming').rmdir()
    moved = next(op for op in plan.operations if op.kind == 'move')
    Path(moved.destination).write_bytes(b'edited completed media')
    monkeypatch.setattr(Sidecars, 'artwork', staticmethod(lambda *args: b'fixture art'))
    with pytest.raises(ValueError, match='target_changed'):
        executor.execute(plan.id, 1, context)
    assert not Path(next(op.destination for op in plan.operations if op.kind == 'create_artwork')).exists()
    assert Path(moved.destination).read_bytes() == b'edited completed media'


def test_pending_media_still_requires_source_root(library, tmp_path, context):
    planner, plan, source, target = make_plan(library, tmp_path, context)
    disconnected = tmp_path / 'disconnected'
    source.parent.rename(disconnected)
    with pytest.raises(ValueError, match='destination_unavailable'):
        Executor(library, planner).execute(plan.id, 1, context)
    assert (disconnected / source.name).read_bytes() == b'original media bytes'
    assert not target.exists()
