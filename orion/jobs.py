"""Durable, bounded local jobs with one filesystem writer."""
from __future__ import annotations
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from orion.models import Job
from orion.discovery import Cancelled
from orion.providers import ProviderError
from orion.store import safe_metadata,is_secret,utcnow

TERMINAL = {'completed','failed','cancelled','interrupted'}
WRITERS = {'organise','undo','sidecars','recovery'}

def serializable(value):
    if hasattr(value,'model_dump'):
        return safe_metadata(value.model_dump(mode='json'))
    if isinstance(value,list):
        return [serializable(v) for v in value]
    if isinstance(value,dict):
        return {k:serializable(v) for k,v in value.items() if not is_secret(k)}
    return value

class Context:
    def __init__(self,manager,job_id,event):
        self.manager,self.job_id,self.event = manager,job_id,event

    def cancelled(self):
        return self.event.is_set() or self.manager._stopping.is_set()

    def progress(self,phase,items_done,items_total,bytes_done=0,bytes_total=0):
        progress = {'phase':phase,'items_done':items_done,'items_total':items_total,'bytes_done':bytes_done,'bytes_total':bytes_total}
        with self.manager.store.transaction() as conn:
            conn.execute('UPDATE orion_jobs SET progress=?,updated_at=? WHERE id=?',(json.dumps(progress),utcnow(),self.job_id))

class JobManager:
    def __init__(self,store,services):
        self.store,self.services = store,services
        self._lock = threading.RLock()
        self._stopping = threading.Event()
        self._events = {}
        self._active_writers = 0
        self._writer = ThreadPoolExecutor(max_workers=1,thread_name_prefix='orion-write')
        self._readers = ThreadPoolExecutor(max_workers=3,thread_name_prefix='orion-read')
        with self.store.transaction() as conn:
            conn.execute("UPDATE orion_jobs SET state='interrupted',cancel=1,updated_at=? WHERE state IN ('queued','running','cancelling')",(utcnow(),))

    @property
    def active_writer_count(self):
        with self._lock:
            return self._active_writers

    @staticmethod
    def _record(row):
        if not row:
            raise KeyError('Job not found')
        return Job(id=row['id'],kind=row['kind'],state=row['state'],progress=json.loads(row['progress']),
                   result=json.loads(row['result']) if row['result'] else None,error=row['error'])

    def get(self,job_id):
        with self.store.transaction() as conn:
            return self._record(conn.execute('SELECT * FROM orion_jobs WHERE id=?',(job_id,)).fetchone())

    def list(self,limit=100):
        with self.store.transaction() as conn:
            return [self._record(r) for r in conn.execute('SELECT * FROM orion_jobs ORDER BY created_at DESC LIMIT ?',(limit,))]

    def _check(self,kind):
        if self._stopping.is_set():
            raise RuntimeError('Orion is stopping')
        if kind not in self.services:
            raise ValueError('Unknown job kind')
        if len(self._events)>=64:
            raise ValueError('Job queue is full; wait for current work')

    def submit(self,kind,payload):
        with self._lock:
            self._check(kind)
            if serializable(payload) != payload:
                raise ValueError('Do not pass credentials in jobs')
            job_id = str(uuid4())
            with self.store.transaction() as conn:
                conn.execute('INSERT INTO orion_jobs(id,kind,state,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                             (job_id,kind,'queued',json.dumps(payload),utcnow(),utcnow()))
            self._schedule(job_id,kind,payload)
        return self.get(job_id)

    def _schedule(self,job_id,kind,payload):
        event = threading.Event()
        self._events[job_id] = event
        pool = self._writer if kind in WRITERS else self._readers
        pool.submit(self._run,job_id,kind,payload,event)

    def _state(self,job_id,state,result=None,error=None):
        with self.store.transaction() as conn:
            conn.execute('UPDATE orion_jobs SET state=?,result=?,error=?,updated_at=? WHERE id=?',
                         (state,json.dumps(result) if result is not None else None,error,utcnow(),job_id))

    def _run(self,job_id,kind,payload,event):
        context = Context(self,job_id,event)
        writer = kind in WRITERS
        active = False
        state,result,error = 'cancelled',None,None
        try:
            if not context.cancelled():
                with self._lock:
                    if writer:
                        self._active_writers += 1
                        active = True
                    self._state(job_id,'running')
                result = serializable(self.services[kind](payload,context))
                if not isinstance(result,dict):
                    result = {'value':result}
                outcome = result.get('state')
                state = 'failed' if outcome in ('failed','partial') else 'cancelled' if outcome=='cancelled' or result.get('cancelled') or (context.cancelled() and outcome!='completed') else 'completed'
                error = outcome if state=='failed' else None
        except Cancelled:
            state = 'cancelled'
        except ProviderError as exc:
            state,error = 'failed',exc.code
        except Exception:
            # Raw request exceptions may contain credential-bearing URLs.
            state,error = 'failed','job_failed'
        finally:
            with self._lock:
                if active:
                    self._active_writers -= 1
                self._events.pop(job_id,None)
                # Publish terminal state after scheduler cleanup under the same
                # lock retry uses, so a terminal job is immediately retryable.
                self._state(job_id,state,result,error)

    def cancel(self,job_id):
        with self._lock:
            job = self.get(job_id)
            if job.state in TERMINAL:
                return job
            event = self._events.get(job_id)
            if event:
                event.set()
            with self.store.transaction() as conn:
                conn.execute("UPDATE orion_jobs SET cancel=1,state=CASE WHEN state='queued' THEN 'cancelled' ELSE 'cancelling' END,updated_at=? WHERE id=? AND state NOT IN ('completed','failed','cancelled','interrupted')",(utcnow(),job_id))
        return self.get(job_id)

    def retry(self,job_id):
        with self._lock:
            job = self.get(job_id)
            self._check(job.kind)
            if job.state not in ('failed','cancelled','interrupted') or job_id in self._events:
                raise ValueError('Only stopped jobs can be retried')
            with self.store.transaction() as conn:
                payload = json.loads(conn.execute('SELECT payload FROM orion_jobs WHERE id=?',(job_id,)).fetchone()[0])
                conn.execute("UPDATE orion_jobs SET state='queued',cancel=0,result=NULL,error=NULL,progress='{}',updated_at=? WHERE id=?",(utcnow(),job_id))
            self._schedule(job_id,job.kind,payload)
        return self.get(job_id)

    def shutdown(self):
        with self._lock:
            if self._stopping.is_set():
                return
            for job_id,event in list(self._events.items()):
                event.set()
                with self.store.transaction() as conn:
                    conn.execute('UPDATE orion_jobs SET cancel=1,updated_at=? WHERE id=?',(utcnow(),job_id))
            self._stopping.set()
        self._writer.shutdown(wait=True)
        self._readers.shutdown(wait=True)
