from pathlib import Path
from orion.watcher import Watcher
from orion.discovery import Discovery

def setup(library,tmp_path):
    root=tmp_path/'watched';root.mkdir()
    source=library.add_source(root,kind='movies')['id']
    now=[1000.0]
    watcher=Watcher(library,Discovery(library),clock=lambda:now[0])
    return root,source,now,watcher

def test_watching_is_opt_in_and_persists_source_configuration(library,tmp_path,context):
    root,sid,now,watcher=setup(library,tmp_path)
    (root/'a.mkv').write_bytes(b'fixture')
    now[0]+=100
    assert watcher.tick(context).queued==0
    watcher.configure(sid,enabled=True,stability_seconds=10)
    assert Watcher(library,Discovery(library)).settings(sid)['enabled'] is True
    assert library.query().total==0

def test_changing_download_waits_for_stability_and_never_auto_approves(library,tmp_path,context):
    root,sid,now,watcher=setup(library,tmp_path)
    file=root/'a.mkv';file.write_bytes(b'partial')
    watcher.configure(sid,enabled=True,stability_seconds=10)
    assert watcher.tick(context).queued==0
    now[0]+=8;file.write_bytes(b'completed download')
    assert watcher.tick(context).queued==0
    now[0]+=8
    assert watcher.tick(context).queued==0
    now[0]+=3
    result=watcher.tick(context)
    assert result.queued==1
    item=library.query().items[0]
    assert item.decision is None and item.status=='pending'
    assert file.read_bytes()==b'completed download'
    assert watcher.tick(context).queued==0

def test_stability_checkpoint_survives_restart(library,tmp_path,context):
    root,sid,now,watcher=setup(library,tmp_path)
    (root/'a.mkv').write_bytes(b'fixture')
    watcher.configure(sid,enabled=True,stability_seconds=10)
    watcher.tick(context)
    now[0]+=11
    resumed=Watcher(library,Discovery(library),clock=lambda:now[0])
    assert resumed.tick(context).queued==1
    assert library.query().total==1

def test_unstable_second_file_cannot_be_indexed_by_source_wide_scan(library,tmp_path,context):
    root,sid,now,watcher=setup(library,tmp_path)
    (root/'ready.mkv').write_bytes(b'ready')
    watcher.configure(sid,enabled=True,stability_seconds=10)
    watcher.tick(context);now[0]+=11
    (root/'still-downloading.mkv').write_bytes(b'partial')
    assert watcher.tick(context).queued==0
    assert library.query().total==0

def test_offline_watch_backs_off_and_retains_existing_items(library,tmp_path,context):
    root,sid,now,watcher=setup(library,tmp_path)
    watcher.configure(sid,enabled=True,stability_seconds=10)
    root.rmdir()
    report=watcher.tick(context)
    assert report.unavailable_sources==[sid]
    assert watcher.settings(sid)['next_attempt']>now[0]
    assert watcher.tick(context).queued==0

def test_download_marker_blocks_stable_media_until_marker_disappears(library,tmp_path,context):
    root,sid,now,watcher=setup(library,tmp_path)
    (root/'a.mkv').write_bytes(b'media');(root/'a.mkv.part').write_bytes(b'partial')
    watcher.configure(sid,enabled=True,stability_seconds=10)
    watcher.tick(context);now[0]+=11
    assert watcher.tick(context).queued==0
    (root/'a.mkv.part').unlink()
    assert watcher.tick(context).queued==0
    now[0]+=11
    assert watcher.tick(context).queued==1

def test_queued_watching_rechecks_arrivals_and_does_not_submit_twice(library,tmp_path,context):
    from types import SimpleNamespace
    root,sid,now,watcher=setup(library,tmp_path)
    media=root/'a.mkv';media.write_bytes(b'media')
    class Queue:
        def __init__(self):self.calls=[]
        def submit(self,kind,payload):
            self.calls.append((kind,payload));return SimpleNamespace(id='queued')
        def get(self,id):return SimpleNamespace(state='running')
    queue=Queue();watcher.jobs=queue
    watcher.configure(sid,enabled=True,stability_seconds=10)
    watcher.tick(context);now[0]+=11
    assert watcher.tick(context).queued==1
    assert watcher.tick(context).queued==0
    assert len(queue.calls)==1 and queue.calls[0][0]=='watch_scan'
    media.write_bytes(b'changed during queue')
    assert watcher.scan_ready(queue.calls[0][1],context)['skipped'] is True
    assert library.query().total==0

def test_failed_queued_scan_backs_off_without_marking_snapshot_processed(library,tmp_path,context):
    from types import SimpleNamespace
    root,sid,now,watcher=setup(library,tmp_path)
    (root/'a.mkv').write_bytes(b'media')
    class Queue:
        def __init__(self):self.calls=[]
        def submit(self,kind,payload):self.calls.append(payload);return SimpleNamespace(id='queued')
        def get(self,id):return SimpleNamespace(state='failed',result=None)
    queue=Queue();watcher.jobs=queue
    watcher.configure(sid,enabled=True,stability_seconds=10)
    watcher.tick(context);now[0]+=11;watcher.tick(context)
    assert watcher.tick(context).queued==0
    assert watcher.settings(sid)['next_attempt']>now[0]
    assert len(queue.calls)==1
