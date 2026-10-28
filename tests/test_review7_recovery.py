import hashlib
import threading
from pathlib import Path

import pytest
from orion.discovery import Discovery
from orion.executor import Executor
from orion.filesystem import Filesystem
from orion.integrations.sidecars import Sidecars
from orion.jobs import JobManager
from orion.models import MatchDecision
from orion.naming import NamingProfile
from orion.planner import Planner, PlanOptions
from orion.watcher import Watcher
from test_jobs import wait_terminal
from tests_support import make_plan


@pytest.mark.parametrize('stop', ['cancelled', 'failed'])
@pytest.mark.parametrize('scan_kind', ['scan', 'watch_scan'])
def test_scan_after_partial_move_preserves_confirmation_for_job_retry(library, tmp_path, context, stop, scan_kind):
    planner, plan, source, target = make_plan(library, tmp_path, context, directory=True)
    iid = plan.operations[0].item_id
    before = library.get(iid)
    moved, release = threading.Event(), threading.Event()

    class StopOnceFilesystem(Filesystem):
        fail = stop == 'failed'
        def rename_noreplace(self, src, dst):
            if Path(src).suffix == '.mkv' and self.fail:
                self.fail = False
                raise OSError('temporary fixture failure')
            return super().rename_noreplace(src, dst)

    class HoldFirstMember(Executor):
        held = False
        def _journal(self, op, state, **details):
            super()._journal(op, state, **details)
            if stop == 'cancelled' and state == 'completed' and not self.held:
                self.held = True
                moved.set()
                assert release.wait(5)

    executor = HoldFirstMember(library, planner, StopOnceFilesystem())
    discovery = Discovery(library)
    watcher = Watcher(library, discovery)
    if scan_kind == 'watch_scan':
        watcher.configure(before.source_id, enabled=True)
    manager = JobManager(library.store, {
        'organise': lambda p, c: executor.execute(p['plan_id'], p['revision'], c),
        scan_kind: watcher.scan_ready if scan_kind == 'watch_scan' else lambda p, c: discovery.scan(p['source_ids'], p['deep'], c),
    })
    try:
        job = manager.submit('organise', {'plan_id': plan.id, 'revision': 1})
        if stop == 'cancelled':
            assert moved.wait(3)
            manager.cancel(job.id)
            release.set()
        assert wait_terminal(manager, job.id).state == stop
        assert len([op for op in executor.operations(plan.id) if op.state == 'completed']) == 1
        scan_payload = {'source_id': before.source_id, 'snapshot': watcher.snapshot(Path(library.sources()[0]['path']), context)} if scan_kind == 'watch_scan' else {'source_ids': [before.source_id], 'deep': True}
        scan = manager.submit(scan_kind, scan_payload)
        assert wait_terminal(manager, scan.id).state == 'completed'
        observed = library.get(iid)
        assert observed.decision == before.decision
        assert observed.signature == before.signature
        manager.retry(job.id)
        assert wait_terminal(manager, job.id).state == 'completed'
        assert target.read_bytes() == b'original media bytes'
        assert library.get(iid).status == 'organised'
    finally:
        release.set()
        manager.shutdown()


def test_scan_preserves_recovery_item_when_only_subtitle_remains(library, tmp_path, context):
    planner, plan, source, target = make_plan(library, tmp_path, context, directory=True)
    iid = plan.operations[0].item_id
    before = library.get(iid)
    class FailSubtitleOnce(Filesystem):
        fail = True
        def rename_noreplace(self, src, dst):
            if Path(src).suffix == '.srt' and self.fail:
                self.fail = False
                raise OSError('temporary fixture failure')
            return super().rename_noreplace(src, dst)
    executor = Executor(library, planner, FailSubtitleOnce())
    assert executor.execute(plan.id, 1, context).state == 'partial'
    Discovery(library).scan([before.source_id], False, context)
    assert library.get(iid).status == 'error'
    assert library.get(iid).decision == before.decision
    assert executor.execute(plan.id, 1, context).state == 'completed'
    assert target.read_bytes() == b'original media bytes'


def test_undo_batch_cannot_be_undone_again(library, tmp_path, context):
    planner, plan, source, target = make_plan(library, tmp_path, context)
    executor = Executor(library, planner)
    forward = executor.execute(plan.id, 1, context)
    undo = executor.undo_plan(forward.batch_id)
    restored = executor.execute(undo.id, 1, context)
    with pytest.raises(ValueError, match='undo'):
        executor.undo_plan(restored.batch_id)
    assert source.read_bytes() == b'original media bytes'
    assert not target.exists()
    assert library.get(plan.operations[0].item_id).status == 'approved'


@pytest.mark.parametrize('container', [False, True])
def test_auto_source_directory_item_owns_embedded_audio_and_books(library, tmp_path, context, container):
    root = tmp_path / 'incoming'
    folder = root / 'Movies' / 'Film' if container else root / 'Film'
    folder.mkdir(parents=True)
    (folder / 'movie.mkv').write_bytes(b'film')
    (folder / 'soundtrack.mp3').write_bytes(b'audio')
    nested = folder / 'Extras'
    nested.mkdir()
    (nested / 'book.epub').write_bytes(b'book')
    (root / 'independent.mp3').write_bytes(b'standalone')
    sid = library.add_source(root)['id']
    Discovery(library).scan([sid], False, context)
    items = library.query().items
    assert {item.path for item in items} == {str(folder), str(root / 'independent.mp3')}
    movie = library.at_path(sid, str(folder))
    assert set(movie.signature['children']) == {'movie.mkv', 'soundtrack.mp3', 'Extras/book.epub'}


@pytest.mark.parametrize('kind', ['music', 'books'])
def test_successful_sidecar_only_inplace_item_finalises_and_undo_restores_status(library, tmp_path, context, monkeypatch, kind):
    root = tmp_path / kind
    root.mkdir()
    media = root / ('Track.mp3' if kind == 'music' else 'Book.epub')
    media.write_bytes(b'unchanged media')
    digest = hashlib.sha256(media.read_bytes()).hexdigest()
    sid = library.add_source(root, kind=kind)['id']
    Discovery(library).scan([sid], False, context)
    item = library.query().items[0]
    library.decide(item.id, MatchDecision(item_id=item.id, metadata={
        'title': media.stem, 'artist': 'Artist', 'album': 'Album', 'author': 'Author',
        'poster_url': 'https://covers.openlibrary.org/b/id/1-M.jpg',
    }))
    monkeypatch.setattr(Sidecars, 'artwork', staticmethod(lambda *args: b'fixture image'))
    planner = Planner(library)
    plan = planner.create([item.id], PlanOptions(in_place=True, profile=NamingProfile(nfo_enabled=True, artwork_enabled=True)))
    assert not plan.issues
    assert plan.operations and all(op.kind.startswith('create_') for op in plan.operations)
    executor = Executor(library, planner)
    result = executor.execute(plan.id, 1, context)
    assert result.state == 'completed'
    final = library.get(item.id)
    assert final.status == 'organised'
    assert final.path == str(media) and final.signature == item.signature
    undo = executor.undo_plan(result.batch_id)
    assert not undo.issues
    assert executor.execute(undo.id, 1, context).state == 'completed'
    assert library.get(item.id).status == 'approved'
    assert library.get(item.id).path == str(media)
    assert hashlib.sha256(media.read_bytes()).hexdigest() == digest
    assert all(not Path(op.destination).exists() for op in plan.operations)

def test_pending_preview_does_not_prevent_changed_media_rescan(library, tmp_path, context):
    planner, plan, source, target = make_plan(library, tmp_path, context)
    iid = plan.operations[0].item_id
    source.write_bytes(b'new media revision')
    Discovery(library).scan([library.get(iid).source_id], False, context)
    assert library.get(iid).decision is None
    assert library.get(iid).status == 'pending'
    assert not target.exists()


def test_sidecar_only_undo_after_clearing_decision_restores_pending(library, tmp_path, context):
    root = tmp_path / 'music'
    root.mkdir()
    media = root / 'Track.mp3'
    media.write_bytes(b'unchanged media')
    sid = library.add_source(root, kind='music')['id']
    Discovery(library).scan([sid], False, context)
    item = library.query().items[0]
    library.decide(item.id, MatchDecision(item_id=item.id, metadata={'title': 'Track', 'artist': 'Artist', 'album': 'Album'}))
    planner = Planner(library)
    plan = planner.create([item.id], PlanOptions(in_place=True, profile=NamingProfile(nfo_enabled=True)))
    executor = Executor(library, planner)
    forward = executor.execute(plan.id, 1, context)
    library.clear_decision(item.id)
    undo = executor.undo_plan(forward.batch_id)
    assert not undo.issues
    assert executor.execute(undo.id, 1, context).state == 'completed'
    final = library.get(item.id)
    assert final.status == 'pending' and final.decision is None
    assert final.path == str(media) and final.signature == item.signature
    assert media.read_bytes() == b'unchanged media'


def test_full_undo_releases_stopped_forward_batch_scan_ownership(library, tmp_path, context):
    planner, base, source, target = make_plan(library, tmp_path, context)
    iid = base.operations[0].item_id
    source.with_suffix('.en.srt').write_bytes(b'subtitle')
    with library.store.transaction() as conn:
        did = conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan = planner.create([iid], PlanOptions(destination_id=did))
    class FailSubtitle(Filesystem):
        def rename_noreplace(self, src, dst):
            if Path(src).suffix == '.srt':
                raise OSError('fixture failure')
            return super().rename_noreplace(src, dst)
    executor = Executor(library, planner, FailSubtitle())
    stopped = executor.execute(plan.id, 1, context)
    assert stopped.state == 'partial'
    undo = executor.undo_plan(stopped.batch_id)
    assert not undo.issues
    assert executor.execute(undo.id, 1, context).state == 'completed'
    source.write_bytes(b'user replaced restored media')
    Discovery(library).scan([library.get(iid).source_id], False, context)
    assert library.get(iid).decision is None
    assert library.get(iid).status == 'pending'
    assert not target.exists()


@pytest.mark.parametrize('stop', ['failed', 'cancelled'])
def test_scan_of_changed_media_after_job_stops_before_first_move(library, tmp_path, context, stop):
    planner, plan, source, target = make_plan(library, tmp_path, context)
    iid = plan.operations[0].item_id
    intent, release = threading.Event(), threading.Event()
    class FailBeforeMove(Filesystem):
        def rename_noreplace(self, src, dst):
            raise OSError('fixture failure before source moves')
    class HoldIntent(Executor):
        def _journal(self, op, state, **details):
            super()._journal(op, state, **details)
            if stop == 'cancelled' and state == 'intent':
                intent.set()
                assert release.wait(5)
    executor = HoldIntent(library, planner, FailBeforeMove() if stop == 'failed' else Filesystem())
    manager = JobManager(library.store, {
        'organise': lambda p, c: executor.execute(plan.id, 1, c),
        'scan': lambda p, c: Discovery(library).scan([library.get(iid).source_id], True, c),
    })
    try:
        job = manager.submit('organise', {'plan_id': plan.id})
        if stop == 'cancelled':
            assert intent.wait(3)
            manager.cancel(job.id)
            release.set()
        assert wait_terminal(manager, job.id).state == stop
        assert source.read_bytes() == b'original media bytes' and not target.exists()
        source.write_bytes(b'user replaced untouched media')
        scan = manager.submit('scan', {})
        assert wait_terminal(manager, scan.id).state == 'completed'
        changed = library.get(iid)
        assert changed.decision is None and changed.status == 'pending'
        assert changed.signature['size'] == len(b'user replaced untouched media')
    finally:
        release.set()
        manager.shutdown()
