from __future__ import annotations
import json
import os
import threading
from pathlib import Path
from uuid import uuid4
from pydantic import Field
from orion.models import Record,Operation,OperationPlan,PlanIssue
from orion.discovery import signature,Cancelled,VIDEO
from orion.filesystem import Filesystem
from orion.planner import contained
from orion.store import utcnow

class BatchResult(Record):
    batch_id: str
    state: str
    completed_operation_ids: list[str] = Field(default_factory=list)
    failed_operation_ids: list[str] = Field(default_factory=list)
    pending_operation_ids: list[str] = Field(default_factory=list)

class RecoverySummary(Record):
    recovered_operation_ids: list[str] = Field(default_factory=list)
    review_operation_ids: list[str] = Field(default_factory=list)

class Executor:
    def __init__(self,library,planner,filesystem=None):
        self.library,self.planner,self.store = library,planner,library.store
        self.fs = filesystem or Filesystem()
        self._lock = threading.RLock()

    def operations(self,plan_id):
        with self.store.transaction() as conn:
            return [Operation.model_validate_json(r['data']) for r in conn.execute('SELECT data FROM orion_operations WHERE plan_id=? ORDER BY rowid',(plan_id,))]

    def _journal(self,op,state,**verification):
        op.state = state
        op.verification.update(verification)
        with self.store.transaction() as conn:
            conn.execute('UPDATE orion_operations SET data=?,updated_at=? WHERE id=?',(op.model_dump_json(),utcnow(),op.id))

    def _batch(self,plan_id):
        with self.store.transaction() as conn:
            row = conn.execute('SELECT id FROM orion_batches WHERE plan_id=? ORDER BY rowid LIMIT 1',(plan_id,)).fetchone()
            if row: return row['id']
            batch_id = str(uuid4())
            conn.execute('INSERT INTO orion_batches VALUES(?,?,?,?,?)',(batch_id,plan_id,'running','{}',utcnow()))
            return batch_id

    def _validate_remaining(self,plan,operations):
        completed = [op for op in operations if op.state == 'completed']
        pending = []
        for original in operations:
            if original.state == 'completed': continue
            op = original.model_copy(deep=True)
            details = op.verification
            item_sig = details.get('item_signature',{})
            if item_sig.get('type') == 'directory':
                children = dict(item_sig['children'])
                for done in completed:
                    if done.item_id == op.item_id:
                        try:
                            relative = Path(done.source).relative_to(Path(details['item_path'])).as_posix()
                            children.pop(relative,None)
                        except ValueError:
                            pass
                details['item_signature'] = {**item_sig,'children':children}
            pending.append(op)
        checked = self.planner._validate(OperationPlan(id=plan.id,revision=plan.revision,operations=pending,issues=plan.issues))
        if checked.issues:
            raise ValueError('Preflight failed: ' + ', '.join(dict.fromkeys(i.code for i in checked.issues)))

    def execute(self,plan_id,revision,context) -> BatchResult:
        with self._lock:
            plan = self.planner.get(plan_id)
            if revision != plan.revision:
                raise ValueError('Plan revision is stale')
            self.reconcile(plan_id,context)
            operations = self.operations(plan_id)
            # A known finalised destination is handled below, not by a fresh
            # preview that would mistake our own published file for a collision.
            regular = [op for op in operations if op.state not in ('completed','finalised')]
            self._validate_remaining(plan,operations if not any(op.state=='finalised' for op in operations) else [*regular,*[op for op in operations if op.state=='completed']])
            batch_id = self._batch(plan_id)
            completed = [op.id for op in operations if op.state=='completed']
            failed,pending = [],[]
            stopped = False
            for index,op in enumerate(operations):
                if op.state == 'completed': continue
                if context.cancelled():
                    stopped = True
                    pending.extend(o.id for o in operations[index:] if o.state!='completed')
                    break
                try:
                    if op.state == 'finalised':
                        self._finish(op,context)
                    else:
                        self._move(op,context,index,len(operations))
                    completed.append(op.id)
                except Cancelled:
                    self._journal(op,'cancelled',error='Cancelled; source retained or publication awaiting recovery')
                    stopped = True
                    pending.extend(o.id for o in operations[index:] if o.state!='completed')
                    break
                except Exception as exc:
                    code = 'destination_exists' if isinstance(exc,FileExistsError) else 'operation_failed'
                    self._journal(op,'error',error=code)
                    self.library.status(op.item_id,'error')
                    failed.append(op.id)
            state = 'cancelled' if stopped else 'partial' if completed and failed else 'failed' if failed else 'completed'
            result = BatchResult(batch_id=batch_id,state=state,completed_operation_ids=completed,failed_operation_ids=failed,pending_operation_ids=pending)
            with self.store.transaction() as conn:
                conn.execute('UPDATE orion_batches SET state=?,data=? WHERE id=?',(state,result.model_dump_json(),batch_id))
                conn.execute('INSERT INTO orion_activity(action,detail,status,created_at) VALUES(?,?,?,?)',('organisation',json.dumps({'batch_id':batch_id,'completed':len(completed),'failed':len(failed)}),state,utcnow()))
            self._update_items_and_directories(operations)
            return result

    def _safe_roots(self,op):
        details = op.verification
        for path_key,root_key,resolved_key in [('source','source_root','source_root_resolved'),('destination','destination_root','destination_root_resolved')]:
            root = Path(details[root_key])
            if str(root.resolve()) != details[resolved_key] or not contained(Path(getattr(op,path_key)),root):
                raise ValueError('Selected path escaped its recorded root')

    def _move(self,op,context,index,total):
        source,destination = Path(op.source),Path(op.destination)
        self._safe_roots(op)
        if signature(source) != op.expected_signature:
            raise ValueError('Source changed')
        digest = self.fs.hash(source,context)
        if signature(source) != op.expected_signature:
            raise ValueError('Source changed during verification')
        mode = 'rename' if self.fs.same_volume(source,destination) else 'copy'
        self._journal(op,'intent',sha256=digest,mode=mode,error=None)
        destination.parent.mkdir(parents=True,exist_ok=True)
        self._safe_roots(op)
        if mode == 'rename':
            if context.cancelled(): raise Cancelled()
            if signature(source) != op.expected_signature:
                raise ValueError('Source changed before rename')
            self.fs.rename_noreplace(source,destination)
            self._journal(op,'finalised',final_signature=signature(destination))
        else:
            temp = destination.parent / ('.orion-' + op.id + '.part')
            if temp.exists():
                owned = op.verification.get('temp_signature')
                if not owned or signature(temp) != owned:
                    raise ValueError('Temporary copy changed or ownership is uncertain')
                if owned.get('size') == op.expected_signature['size'] and self.fs.hash(temp,context) == digest:
                    self._journal(op,'verified',temp_signature=signature(temp))
                    self._safe_roots(op)
                    self.fs.rename_noreplace(temp,destination)
                    self._journal(op,'finalised',final_signature=signature(destination))
                    self._finish(op,context)
                    context.progress('Organising',index+1,total,int(op.expected_signature['size']),int(op.expected_signature['size']))
                    return
                temp.unlink()
            self._journal(op,'copying',temp_path=str(temp),bytes_done=0)
            def checkpoint(copied,partial_digest,temp_sig):
                self._journal(op,'copying',bytes_done=copied,partial_sha256=partial_digest,temp_signature=temp_sig)
                if copied:
                    context.progress('Copying',index,total,copied,int(op.expected_signature['size']))
            copied,copied_hash = self.fs.copy(source,temp,context,checkpoint)
            if context.cancelled(): raise Cancelled()
            if signature(source) != op.expected_signature or copied != op.expected_signature['size'] or copied_hash != digest or self.fs.hash(temp,context) != digest:
                raise ValueError('Copy verification failed; preserve the source')
            self._journal(op,'verified',temp_signature=signature(temp))
            self._safe_roots(op)
            self.fs.rename_noreplace(temp,destination)
            self._journal(op,'finalised',final_signature=signature(destination))
        self._finish(op,context)
        context.progress('Organising',index+1,total,int(op.expected_signature['size']),int(op.expected_signature['size']))

    def _destination_matches(self,op,context=None):
        destination = Path(op.destination)
        details = op.verification
        if not destination.is_file() or destination.is_symlink() or not details.get('sha256'):
            return False
        observed = signature(destination)
        expected = details.get('final_signature') or (details.get('temp_signature') if details.get('mode')=='copy' else op.expected_signature)
        if not expected or any(observed.get(key) != expected.get(key) for key in ('device','inode','size','mtime_ns')):
            return False
        return self.fs.hash(destination,context) == details['sha256']

    def _finish(self,op,context):
        self._safe_roots(op)
        if not self._destination_matches(op,context):
            raise ValueError('Published destination changed; preserve any source')
        source = Path(op.source)
        if source.exists():
            if context.cancelled(): raise Cancelled()
            if signature(source) != op.expected_signature or self.fs.hash(source,context) != op.verification['sha256']:
                raise ValueError('Source changed; do not delete it')
            self.fs.remove_source(source,op.expected_signature)
        self._journal(op,'completed',final_signature=signature(Path(op.destination)),error=None)

    def reconcile(self,plan_id=None,context=None) -> RecoverySummary:
        with self._lock:
            with self.store.transaction() as conn:
                rows = conn.execute('SELECT data FROM orion_operations' + (' WHERE plan_id=?' if plan_id else ''),(plan_id,) if plan_id else ()).fetchall()
            report = RecoverySummary()
            for row in rows:
                if context and context.cancelled(): raise Cancelled()
                op = Operation.model_validate_json(row['data'])
                if op.state in ('pending','completed'): continue
                try:
                    self._safe_roots(op)
                    if self._destination_matches(op,context):
                        source = Path(op.source)
                        state = 'finalised' if source.exists() else 'completed'
                        self._journal(op,state,final_signature=signature(Path(op.destination)))
                        report.recovered_operation_ids.append(op.id)
                    elif Path(op.destination).exists():
                        self._journal(op,'error',error='destination_identity_uncertain')
                        report.review_operation_ids.append(op.id)
                except (OSError,ValueError):
                    report.review_operation_ids.append(op.id)
            return report

    def _update_items_and_directories(self,operations):
        by_item = {}
        for op in operations:
            by_item.setdefault(op.item_id,[]).append(op)
        for iid,group in by_item.items():
            if not all(op.state=='completed' for op in group): continue
            item = self.library.get(iid)
            destinations = [Path(op.destination) for op in group]
            directory = group[0].verification.get('source_directory')
            undo = group[0].verification.get('undo_of')
            if directory:
                root = Path(directory)
                if root.is_dir():
                    for current,dirs,files in os.walk(root,topdown=False,followlinks=False):
                        try:
                            Path(current).rmdir()
                        except OSError:
                            pass
            target = Path(group[0].verification['restore_item_path']) if undo else Path(os.path.commonpath([str(p.parent) for p in destinations])) if directory else destinations[0]
            item.path = str(target)
            if target.exists():
                item.signature = signature(target)
            item.status = 'approved' if undo else 'organised'
            self.library.upsert(item)

    def undo_plan(self,batch_id) -> OperationPlan:
        with self.store.transaction() as conn:
            row = conn.execute('SELECT plan_id FROM orion_batches WHERE id=?',(batch_id,)).fetchone()
        if not row:
            raise KeyError('Batch not found')
        originals = self.operations(row['plan_id'])
        plan = OperationPlan(id=str(uuid4()))
        for op in originals:
            if op.state != 'completed': continue
            source,destination = Path(op.destination),Path(op.source)
            details = op.verification
            if not self._destination_matches(op):
                plan.issues.append(PlanIssue(code='target_changed',detail='Organised file changed; retain it',item_id=op.item_id))
                continue
            item = self.library.get(op.item_id)
            inverse = Operation(id=str(uuid4()),plan_id=plan.id,item_id=op.item_id,source=str(source),destination=str(destination),expected_signature=details['final_signature'],
                                verification={'source_root':details['destination_root'],'destination_root':details['source_root'],
                                              'source_root_resolved':details['destination_root_resolved'],'destination_root_resolved':details['source_root_resolved'],
                                              'item_path':str(source),'item_signature':details['final_signature'],'item_decision':item.decision.model_dump() if item.decision else None,
                                              'source_directory':str(item.path) if details.get('source_directory') else '',
                                              'undo_of':batch_id,'restore_item_path':details['item_path']})
            plan.operations.append(inverse)
        return self.planner.save(self.planner._validate(plan))
