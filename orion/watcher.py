"""Opt-in polling that queues discovery only after the whole source is stable."""
from __future__ import annotations
import json
import os
import threading
import time
from pathlib import Path
from pydantic import Field
from orion.discovery import Discovery, ScanSummary, linked, signature, Cancelled
from orion.jobs import TERMINAL

class WatchSummary(ScanSummary):
    queued: int = 0
    job_ids: list[str] = Field(default_factory=list)

class Watcher:
    def __init__(self, library, discovery: Discovery, clock=time.time, jobs=None):
        self.library, self.discovery, self.clock, self.jobs = library, discovery, clock, jobs
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None

    def settings(self, source_id):
        source = next((s for s in self.library.sources() if s['id']==source_id), None)
        if not source:
            raise KeyError('Source not found')
        with self.library.store.transaction() as conn:
            row = conn.execute('SELECT value FROM orion_settings WHERE key=?', ('watch_'+source_id,)).fetchone()
        data = json.loads(row[0]) if row else {}
        return {'enabled':bool(source['watch']), 'identify_arrivals':bool(data.get('identify_arrivals',False)), 'stability_seconds':data.get('stability_seconds',30), 'next_attempt':data.get('next_attempt',0)}

    def _load(self, sid):
        with self.library.store.transaction() as conn:
            row = conn.execute('SELECT value FROM orion_settings WHERE key=?',('watch_'+sid,)).fetchone()
        return json.loads(row[0]) if row else {}

    def _save(self, sid, data):
        with self.library.store.transaction() as conn:
            conn.execute('INSERT OR REPLACE INTO orion_settings VALUES(?,?)',('watch_'+sid,json.dumps(data)))

    def configure(self, source_id, *, enabled, stability_seconds=30, identify_arrivals=False):
        if not 5 <= stability_seconds <= 3600:
            raise ValueError('Stability interval must be between 5 and 3600 seconds')
        with self._lock:
            self.settings(source_id)
            with self.library.store.transaction() as conn:
                archived = conn.execute('SELECT value FROM orion_settings WHERE key=?',('source_archived_'+source_id,)).fetchone()
                if enabled and archived and archived[0]=='true':
                    raise ValueError('Resume this source before enabling watching')
                conn.execute('UPDATE orion_sources SET watch=? WHERE id=?',(int(enabled),source_id))
            data = self._load(source_id)
            data.update(stability_seconds=stability_seconds,identify_arrivals=identify_arrivals,next_attempt=0)
            self._save(source_id,data)
            self._wake.set()
        return self.settings(source_id)

    @staticmethod
    def snapshot(root, context):
        if not root.is_dir() or linked(root):
            raise OSError('Source unavailable')
        result = {}
        errors = []
        for directory, dirs, files in os.walk(root, followlinks=False, onerror=errors.append):
            if context.cancelled():
                raise Cancelled()
            dirs[:] = sorted(d for d in dirs if not linked(Path(directory)/d))
            for name in sorted(files):
                path = Path(directory)/name
                if not linked(path) and path.is_file():
                    result[path.relative_to(root).as_posix()] = signature(path)
        if errors:
            raise OSError('Source unavailable')
        return result

    def scan_ready(self, payload, context):
        sid = payload['source_id']
        source = next(s for s in self.library.sources() if s['id']==sid)
        if not source['watch']:
            return {'skipped':True}
        if self.snapshot(Path(source['path']),context) != payload['snapshot']:
            return {'skipped':True, 'reason':'source_changed'}
        with self.library.store.transaction() as conn:
            before = {row['id']:row['signature'] for row in conn.execute('SELECT id,signature FROM orion_items WHERE source_id=?',(sid,))}
        result = self.discovery.scan([sid],False,context)
        if self.settings(sid)['identify_arrivals'] and self.jobs and not result.cancelled and not result.unavailable_sources:
            with self.library.store.transaction() as conn:
                rows = conn.execute("SELECT id,signature FROM orion_items WHERE source_id=? AND decision IS NULL AND status='pending'",(sid,)).fetchall()
            for row in rows:
                if context.cancelled():raise Cancelled()
                if before.get(row['id']) != row['signature']:
                    try:
                        self.jobs.submit('lookup',{'item_id':row['id'],'signature':json.loads(row['signature'])})
                    except ValueError:
                        self.library.annotate(row['id'],lookup_state='error',lookup_error='watch_lookup_queue_full')
        return result

    def tick(self, context):
        report = WatchSummary()
        with self._lock:
            for source in self.library.sources():
                if context.cancelled():
                    report.cancelled = True
                    break
                if not source['watch']:
                    continue
                sid, now = source['id'], self.clock()
                data = self._load(sid)
                if now < data.get('next_attempt',0):
                    continue
                try:
                    snapshot = self.snapshot(Path(source['path']),context)
                except OSError:
                    report.unavailable_sources.append(sid)
                    data['next_attempt'] = now+min(3600,max(30,data.get('backoff',15)*2))
                    data['backoff'] = data['next_attempt']-now
                    self._save(sid,data)
                    continue
                data.update(next_attempt=0,backoff=0)
                pending = data.get('pending_job')
                if pending and self.jobs:
                    job = self.jobs.get(pending)
                    if job.state not in TERMINAL:
                        continue
                    outcome = job.result or {}
                    if job.state=='completed' and not outcome.get('skipped') and not outcome.get('unavailable_sources') and not outcome.get('cancelled'):
                        data['processed'] = data.pop('pending_snapshot',{})
                    data.pop('pending_job',None)
                    if job.state!='completed' or outcome.get('unavailable_sources') or outcome.get('cancelled'):
                        data['next_attempt'] = now+60
                        self._save(sid,data)
                        continue
                if snapshot != data.get('observed'):
                    data.update(observed=snapshot,stable_since=now)
                elif snapshot != data.get('processed') and now-data.get('stable_since',now)>=data.get('stability_seconds',30):
                    downloading = any(Path(p).suffix.lower() in ('.part','.crdownload','.download','.tmp') for p in snapshot)
                    if not downloading:
                        if self.jobs:
                            job = self.jobs.submit('watch_scan',{'source_id':sid,'snapshot':snapshot})
                            data.update(pending_job=job.id,pending_snapshot=snapshot)
                            report.job_ids.append(job.id)
                        else:
                            scanned = self.discovery.scan([sid],False,context)
                            report.processed += scanned.processed
                            report.unchanged += scanned.unchanged
                            report.unavailable_sources.extend(scanned.unavailable_sources)
                            if not scanned.cancelled and not scanned.unavailable_sources:
                                data['processed'] = snapshot
                        report.queued += 1
                self._save(sid,data)
        return report

    def start(self):
        if self._thread:
            return
        watcher = self
        class PollContext:
            def cancelled(self): return watcher._stop.is_set()
            def progress(self,*args): pass
        def run():
            while not self._stop.is_set():
                try:
                    self.tick(PollContext())
                except Cancelled:
                    break
                except Exception:
                    # Retry later without leaking filesystem or provider exceptions.
                    pass
                self._wake.wait(10)
                self._wake.clear()
        self._thread = threading.Thread(target=run,name='orion-watch',daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
