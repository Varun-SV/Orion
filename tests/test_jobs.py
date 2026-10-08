import threading
import time
import pytest
from orion.jobs import JobManager
from orion.store import utcnow

def wait_terminal(manager,job_id):
    deadline = time.monotonic()+5
    while time.monotonic()<deadline:
        job = manager.get(job_id)
        if job.state in ('completed','failed','cancelled','interrupted'): return job
        time.sleep(0.01)
    pytest.fail('Job did not finish')

def test_jobs_persist_progress_and_result(library):
    def scan(payload,context):
        context.progress('Scanning',1,2,4,8)
        return {'processed':2}
    manager = JobManager(library.store,{'scan':scan})
    try:
        job = manager.submit('scan',{})
        result = wait_terminal(manager,job.id)
        assert result.state == 'completed'
        assert result.progress['items_done'] == 1
        assert result.result == {'processed':2}
    finally:
        manager.shutdown()
    reopened = JobManager(library.store,{'scan':scan})
    try:
        assert reopened.get(job.id).result == {'processed':2}
    finally:
        reopened.shutdown()

def test_filesystem_writers_run_one_at_a_time(library):
    started,release = threading.Event(),threading.Event()
    phases = []
    def organise(payload,context):
        phases.append(payload['id'])
        started.set()
        assert release.wait(3)
        return {'state':'completed'}
    manager = JobManager(library.store,{'organise':organise})
    try:
        first = manager.submit('organise',{'id':1})
        assert started.wait(3)
        second = manager.submit('organise',{'id':2})
        assert manager.active_writer_count == 1
        assert manager.get(second.id).state == 'queued'
        assert phases == [1]
        release.set()
        assert wait_terminal(manager,first.id).state == 'completed'
        assert wait_terminal(manager,second.id).state == 'completed'
        assert phases == [1,2]
    finally:
        release.set()
        manager.shutdown()

def test_cancel_is_durable_and_cooperative(library):
    started = threading.Event()
    def scan(payload,context):
        started.set()
        while not context.cancelled(): time.sleep(0.005)
        return {'cancelled':True}
    manager = JobManager(library.store,{'scan':scan})
    try:
        job = manager.submit('scan',{})
        assert started.wait(3)
        manager.cancel(job.id)
        assert wait_terminal(manager,job.id).state == 'cancelled'
        with library.store.transaction() as conn:
            assert conn.execute('SELECT cancel FROM orion_jobs WHERE id=?',(job.id,)).fetchone()[0] == 1
    finally:
        manager.shutdown()

def test_startup_marks_abandoned_jobs_interrupted(library):
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_jobs(id,kind,state,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                     ('abandoned','scan','running','{}',utcnow(),utcnow()))
    manager = JobManager(library.store,{'scan':lambda p,c:{'processed':1}})
    try:
        assert manager.get('abandoned').state == 'interrupted'
        retried = manager.retry('abandoned')
        assert retried.id == 'abandoned'
        assert wait_terminal(manager,retried.id).state == 'completed'
    finally:
        manager.shutdown()

def test_failed_job_can_retry_without_logging_exception_secrets(library):
    attempts = []
    def fail_once(payload,context):
        attempts.append(1)
        if len(attempts)==1: raise RuntimeError('secret-token-value')
        return {'ok':True}
    manager = JobManager(library.store,{'scan':fail_once})
    try:
        job = manager.submit('scan',{})
        failed = wait_terminal(manager,job.id)
        assert failed.state == 'failed'
        assert 'secret-token-value' not in failed.model_dump_json()
        manager.retry(job.id)
        assert wait_terminal(manager,job.id).result == {'ok':True}
    finally:
        manager.shutdown()

def test_shutdown_cancels_active_jobs_and_rejects_submissions(library):
    started = threading.Event()
    def scan(payload,context):
        started.set()
        while not context.cancelled(): time.sleep(0.005)
        return {'cancelled':True}
    manager = JobManager(library.store,{'scan':scan})
    job = manager.submit('scan',{})
    assert started.wait(3)
    manager.shutdown()
    assert manager.get(job.id).state == 'cancelled'
    with pytest.raises(RuntimeError): manager.submit('scan',{})

def test_read_workers_are_bounded_without_blocking_writer(library):
    release = threading.Event()
    enough = threading.Event()
    running = []
    lock = threading.Lock()
    def scan(payload,context):
        with lock:
            running.append(payload['id'])
            if len(running)==3: enough.set()
        assert release.wait(3)
        return {'ok':True}
    manager = JobManager(library.store,{'scan':scan,'organise':lambda p,c:{'state':'completed'}})
    try:
        jobs = [manager.submit('scan',{'id':i}) for i in range(4)]
        assert enough.wait(3)
        assert manager.get(jobs[3].id).state == 'queued'
        writer = manager.submit('organise',{})
        assert wait_terminal(manager,writer.id).state == 'completed'
        release.set()
        assert all(wait_terminal(manager,j.id).state=='completed' for j in jobs)
    finally:
        release.set()
        manager.shutdown()

def test_job_payload_never_persists_credentials(library):
    manager = JobManager(library.store,{'scan':lambda p,c:{}})
    try:
        with pytest.raises(ValueError):
            manager.submit('scan',{'api_key':'do-not-store'})
        with library.store.transaction() as conn:
            assert conn.execute('SELECT COUNT(*) FROM orion_jobs').fetchone()[0] == 0
    finally:
        manager.shutdown()

def test_retry_keeps_verified_completed_operations(library,tmp_path,context):
    from tests_support import make_plan
    from orion.executor import Executor
    from orion.filesystem import Filesystem
    planner,plan,source,target = make_plan(library,tmp_path,context,directory=True)
    class FailOnce(Filesystem):
        failed = False
        def rename_noreplace(self,src,dst):
            if str(src).endswith('.mkv') and not self.failed:
                self.failed = True
                raise OSError('temporary fault')
            super().rename_noreplace(src,dst)
    executor = Executor(library,planner,filesystem=FailOnce())
    manager = JobManager(library.store,{'organise':lambda p,c:executor.execute(p['plan_id'],p['revision'],c)})
    try:
        job = manager.submit('organise',{'plan_id':plan.id,'revision':1})
        first = wait_terminal(manager,job.id)
        assert first.state == 'failed'
        assert len(first.result['completed_operation_ids']) == 1
        assert library.query(status='error').total == 1
        manager.retry(job.id)
        final = wait_terminal(manager,job.id)
        assert final.state == 'completed'
        assert len(final.result['completed_operation_ids']) == 2
        assert target.read_bytes() == b'original media bytes'
    finally:
        manager.shutdown()

def test_retry_cannot_race_terminal_job_cleanup(library):
    published,release,settled = threading.Event(),threading.Event(),threading.Event()
    attempts = []
    def service(payload,context):
        attempts.append(1)
        if len(attempts)==1: raise RuntimeError('first failure')
        return {'ok':True}
    class DelayedFinalisation(JobManager):
        def _state(self,job_id,state,*a,**kw):
            super()._state(job_id,state,*a,**kw)
            if state=='failed':
                published.set()
                assert release.wait(3)
    manager = DelayedFinalisation(library.store,{'scan':service})
    outcomes = []
    try:
        job = manager.submit('scan',{})
        assert published.wait(3)
        def retry():
            try:
                manager.retry(job.id)
                outcomes.append('retried')
            except Exception as exc:
                outcomes.append(type(exc).__name__)
            finally:
                settled.set()
        thread = threading.Thread(target=retry)
        thread.start()
        settled.wait(0.2)
        release.set()
        thread.join(3)
        assert outcomes == ['retried']
        assert wait_terminal(manager,job.id).state == 'completed'
    finally:
        release.set()
        manager.shutdown()
