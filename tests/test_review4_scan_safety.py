import os
import threading
from pathlib import Path
import pytest
from orion.discovery import Discovery
from orion.executor import Executor
from orion.jobs import JobManager
from orion.watcher import Watcher
from test_jobs import wait_terminal
from tests_support import make_plan

@pytest.mark.parametrize('check',['shallow','deep','watcher'])
def test_source_ancestry_is_revalidated_after_registration(library,tmp_path,context,check):
    parent=tmp_path/'normal';source=parent/'incoming';source.mkdir(parents=True)
    (source/'original.mkv').write_bytes(b'original media')
    sid=library.add_source(source,kind='movies')['id']
    Discovery(library).scan([sid],False,context)
    before=library.query().items[0]
    foreign=tmp_path/'foreign';(foreign/'incoming').mkdir(parents=True)
    (foreign/'incoming'/'outside.mkv').write_bytes(b'outside registered ancestry')
    original=tmp_path/'original-parent';parent.rename(original)
    if os.name=='nt':
        import _winapi
        _winapi.CreateJunction(str(foreign),str(parent))
    else:parent.symlink_to(foreign,target_is_directory=True)
    try:
        assert source.is_dir() and not source.is_symlink()
        if check=='watcher':
            with pytest.raises(OSError,match='unavailable'):Watcher.snapshot(source,context)
        else:
            report=Discovery(library).scan([sid],check=='deep',context)
            assert report.unavailable_sources==[sid] and report.processed==0
        assert library.query().items==[before]
    finally:
        parent.rmdir() if os.name=='nt' else parent.unlink()
        original.rename(parent)

@pytest.mark.parametrize('scan_kind',['scan','watch_scan'])
def test_discovery_waits_for_partially_moved_directory(library,tmp_path,context,scan_kind):
    planner,plan,source,target=make_plan(library,tmp_path,context,directory=True)
    iid=plan.operations[0].item_id;sid=library.get(iid).source_id
    moved=threading.Event();release=threading.Event();scanned=threading.Event()
    class BlockAfterFirstMove(Executor):
        held=False
        def _journal(self,op,state,**details):
            super()._journal(op,state,**details)
            if state=='completed' and not self.held:
                self.held=True;moved.set()
                assert release.wait(5)
    executor=BlockAfterFirstMove(library,planner)
    discovery=Discovery(library);watcher=Watcher(library,discovery)
    watcher.configure(sid,enabled=True,stability_seconds=5)
    snapshot=watcher.snapshot(Path(library.sources()[0]['path']),context)
    def scan(payload,job_context):
        scanned.set()
        return watcher.scan_ready(payload,job_context) if scan_kind=='watch_scan' else discovery.scan([sid],False,job_context)
    manager=JobManager(library.store,{'organise':lambda p,c:executor.execute(plan.id,1,c),scan_kind:scan})
    try:
        writer=manager.submit('organise',{});assert moved.wait(3)
        read=manager.submit(scan_kind,{'source_id':sid,'snapshot':snapshot} if scan_kind=='watch_scan' else {})
        assert not scanned.wait(.3)
        assert manager.get(read.id).state=='queued'
        assert library.get(iid).decision is not None
        release.set()
        assert wait_terminal(manager,writer.id).state=='completed'
        assert wait_terminal(manager,read.id).state=='completed'
        assert scanned.is_set()
        item=library.get(iid)
        assert item.status=='organised' and item.decision is not None
        assert Path(item.path)==target.parent
        assert target.read_bytes()==b'original media bytes'
    finally:release.set();manager.shutdown()
