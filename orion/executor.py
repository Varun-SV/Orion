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
from orion.planner import contained,case_only_rename,exact_name_exists
from orion.store import utcnow,normalized

class BatchResult(Record):
    batch_id: str
    state: str
    completed_operation_ids: list[str] = Field(default_factory=list)
    failed_operation_ids: list[str] = Field(default_factory=list)
    pending_operation_ids: list[str] = Field(default_factory=list)
    skipped_operation_ids: list[str] = Field(default_factory=list)
    created_sidecars_removed: list[str] = Field(default_factory=list)
    recovery_item_ids: list[str] = Field(default_factory=list)

class RecoverySummary(Record):
    recovered_batch_ids: list[str] = Field(default_factory=list)
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
            if op.state=='staged' and details.get('mode')=='case_rename':
                op.source = details['temp_path']
                details['item_path'] = op.source
                details['item_signature'] = op.expected_signature
            item_sig = details.get('item_signature',{})
            if item_sig.get('type') == 'directory':
                children = dict(item_sig['children'])
                for done in completed:
                    if done.item_id == op.item_id and done.kind == 'move':
                        try:
                            relative = Path(done.source).relative_to(Path(details['item_path'])).as_posix()
                            children.pop(relative,None)
                        except ValueError:
                            pass
                details['item_signature'] = {**item_sig,'children':children}
            if item_sig.get('type') == 'file':
                primary = [done for done in completed if done.item_id==op.item_id and done.kind=='move' and done.source==details.get('item_path')]
                if primary:
                    details['completed_dependencies'] = [done.model_dump() for done in primary]
            if op.kind.startswith('create_') and details.get('dependencies'):
                dependencies = [done for done in completed if done.id in details['dependencies']]
                if len(dependencies)==len(details['dependencies']):
                    details['completed_dependencies'] = [done.model_dump() for done in dependencies]
            pending.append(op)
        checked = self.planner._validate(OperationPlan(id=plan.id,revision=plan.revision,operations=pending,issues=plan.issues))
        if checked.issues:
            raise ValueError('Preflight failed: ' + ', '.join(dict.fromkeys(i.code for i in checked.issues)))

    def execute(self,plan_id,revision,context) -> BatchResult:
        with self._lock:
            plan = self.planner.get(plan_id)
            if revision != plan.revision:
                raise ValueError('Plan revision is stale')
            if plan.undo_batch_id:
                with self.store.transaction() as conn:
                    original=conn.execute('SELECT plan_id FROM orion_batches WHERE id=?',(plan.undo_batch_id,)).fetchone()
                states={op.id:op.state for op in self.operations(original['plan_id'])} if original else None
                if plan.undo_operation_states is None or states!=plan.undo_operation_states:
                    raise ValueError('Undo preview is stale; create a new preview for this batch')
            self.reconcile(plan_id,context)
            operations = self.operations(plan_id)
            if plan.undo_batch_id and self._restore_conflicts(plan,operations):
                raise ValueError('Undo restore conflict: the original location contains unexpected files or another indexed item')
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
                    if op.kind.startswith('create_'):
                        if any(other.state!='completed' for other in operations if other.id in op.verification.get('dependencies',[])):
                            raise ValueError('Media dependencies have not completed')
                        self._create(op,context,index,len(operations))
                    elif op.kind == 'remove_created':
                        self._remove_created(op,context)
                    elif op.state == 'finalised':
                        self._finish(op,context,index,len(operations))
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
                    if op.kind == 'move':self.library.status(op.item_id,'error')
                    failed.append(op.id)
            return self._complete_batch(plan,operations,batch_id,completed,failed,pending,stopped)

    def _complete_batch(self,plan,operations,batch_id,completed,failed,pending,stopped=False):
        recovery_items = self._update_items_and_directories(operations)
        state = 'cancelled' if stopped else 'partial' if completed and failed else 'failed' if failed else 'partial' if plan.excluded_operation_ids or recovery_items else 'completed'
        result = BatchResult(batch_id=batch_id,state=state,recovery_item_ids=recovery_items,skipped_operation_ids=plan.excluded_operation_ids,completed_operation_ids=completed,failed_operation_ids=failed,pending_operation_ids=pending,created_sidecars_removed=[op.source for op in operations if op.kind=='remove_created' and op.state=='completed'])
        with self.store.transaction() as conn:
            previous=conn.execute('SELECT state,data FROM orion_batches WHERE id=?',(batch_id,)).fetchone()
            conn.execute('UPDATE orion_batches SET state=?,data=? WHERE id=?',(state,result.model_dump_json(),batch_id))
            if previous['state']!=state or previous['data']!=result.model_dump_json():
                conn.execute('INSERT INTO orion_activity(action,detail,status,created_at) VALUES(?,?,?,?)',('undo' if plan.undo_batch_id else 'organisation',json.dumps({'batch_id':batch_id,'undo_batch_id':plan.undo_batch_id,'completed':len(completed),'failed':len(failed),'recovery_item_ids':recovery_items}),state,utcnow()))
        return result

    def _safe_roots(self,op):
        details = op.verification
        for path_key,root_key,resolved_key in [('source','source_root','source_root_resolved'),('destination','destination_root','destination_root_resolved')]:
            if path_key=='source' and op.kind.startswith('create_'):
                continue
            root = Path(details[root_key])
            if str(root.resolve()) != details[resolved_key] or not contained(Path(getattr(op,path_key)),root):
                raise ValueError('Selected path escaped its recorded root')

    def _move(self,op,context,index,total):
        source,destination = Path(op.source),Path(op.destination)
        self._safe_roots(op)
        if op.state=='staged' and op.verification.get('mode')=='case_rename':
            self._publish_case_rename(op,context,index,total)
            return
        if signature(source) != op.expected_signature:
            raise ValueError('Source changed')
        digest = self.fs.hash(source,context)
        if signature(source) != op.expected_signature:
            raise ValueError('Source changed during verification')
        mode = 'case_rename' if case_only_rename(source,destination) else 'rename' if self.fs.same_volume(source,destination) else 'copy'
        temp = source.parent / ('.orion-' + op.id + '.part') if mode=='case_rename' else None
        self._journal(op,'intent',sha256=digest,mode=mode,error=None,**({'temp_path':str(temp)} if temp else {}))
        destination.parent.mkdir(parents=True,exist_ok=True)
        self._safe_roots(op)
        if mode == 'case_rename':
            if context.cancelled():raise Cancelled()
            if signature(source) != op.expected_signature:
                raise ValueError('Source changed before case rename')
            self.fs.rename_noreplace(source,temp)
            self._journal(op,'staged',temp_signature=signature(temp))
            self._publish_case_rename(op,context,index,total)
            return
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
                observed = signature(temp)
                identity_matches = owned and all(observed.get(key)==owned.get(key) for key in ('type','device','inode','size'))
                full_copy = identity_matches and owned.get('size')==op.expected_signature['size'] and op.verification.get('partial_sha256')==digest
                # copystat may change mtime before its next journal checkpoint.
                # Accept that boundary only for the same complete inode AND hash.
                if not owned or observed != owned and not (full_copy and self.fs.hash(temp,context)==digest):
                    raise ValueError('Temporary copy changed or ownership is uncertain')
                if owned.get('size') == op.expected_signature['size'] and self.fs.hash(temp,context) == digest:
                    self._journal(op,'verified',temp_signature=signature(temp))
                    self._safe_roots(op)
                    self.fs.rename_noreplace(temp,destination)
                    self._journal(op,'finalised',final_signature=signature(destination))
                    self._finish(op,context,index,total)
                    context.progress('Organising',index+1,total,int(op.expected_signature['size']),int(op.expected_signature['size']))
                    return
                temp.unlink()
            self._journal(op,'copying',temp_path=str(temp),bytes_done=0)
            def checkpoint(copied,partial_digest,temp_sig):
                self._journal(op,'copying',bytes_done=copied,partial_sha256=partial_digest,temp_signature=temp_sig)
                if copied:
                    context.progress('Copying',index,total,copied,int(op.expected_signature['size']))
            copied,copied_hash = self.fs.copy(source,temp,context,checkpoint)
            context.progress('Verifying copy',index,total,copied,int(op.expected_signature['size']))
            if context.cancelled(): raise Cancelled()
            if signature(source) != op.expected_signature or copied != op.expected_signature['size'] or copied_hash != digest or self.fs.hash(temp,context) != digest:
                raise ValueError('Copy verification failed; preserve the source')
            self._journal(op,'verified',temp_signature=signature(temp))
            context.progress('Finalising',index,total,copied,int(op.expected_signature['size']))
            self._safe_roots(op)
            self.fs.rename_noreplace(temp,destination)
            self._journal(op,'finalised',final_signature=signature(destination))
        self._finish(op,context,index,total)
        context.progress('Organising',index+1,total,int(op.expected_signature['size']),int(op.expected_signature['size']))

    def _publish_case_rename(self,op,context,index,total):
        temp = Path(op.verification['temp_path'])
        if temp != Path(op.source).parent / ('.orion-' + op.id + '.part') or not contained(temp,Path(op.verification['source_root'])):
            raise ValueError('Case rename staging path escaped its recorded root')
        self._safe_roots(op)
        if signature(temp) != op.expected_signature or self.fs.hash(temp,context) != op.verification['sha256']:
            raise ValueError('Staged case rename changed; retain it for review')
        if context.cancelled():raise Cancelled()
        self.fs.rename_noreplace(temp,Path(op.destination))
        self._journal(op,'finalised',final_signature=signature(Path(op.destination)))
        self._finish(op,context,index,total)

    def _create(self,op,context,index,total):
        from orion.integrations.sidecars import Sidecars
        import hashlib
        destination = Path(op.destination)
        self._safe_roots(op)
        if op.state=='finalised':
            if not self._destination_matches(op,context):raise ValueError('Generated output changed')
            self._journal(op,'completed',error=None)
            return
        destination.parent.mkdir(parents=True,exist_ok=True)
        self._safe_roots(op)
        temp = destination.parent/('.orion-'+op.id+'.part')
        if temp.exists():
            owned = op.verification.get('temp_signature')
            if not owned or signature(temp)!=owned:raise ValueError('Temporary output ownership uncertain')
            if op.verification.get('generated_complete') and self.fs.hash(temp,context)==op.verification.get('sha256'):
                self.fs.rename_noreplace(temp,destination)
                self._journal(op,'completed',final_signature=signature(destination),error=None)
                return
            temp.unlink()
        self._journal(op,'intent',mode='create',error=None)
        data = Sidecars.artwork(op.verification['artwork_url'],context) if op.kind=='create_artwork' else op.verification['content'].encode('utf-8')
        if context.cancelled():raise Cancelled()
        self._safe_roots(op)
        with temp.open('xb') as output:
            self._journal(op,'creating',temp_path=str(temp),temp_signature=signature(temp),generated_complete=False)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
            digest = hashlib.sha256(data).hexdigest()
            self._journal(op,'verified',temp_signature=signature(temp),sha256=digest,generated_complete=True,bytes_done=len(data))
        self.fs.sync_directory(temp.parent)
        if context.cancelled():raise Cancelled()
        self._safe_roots(op)
        if self.fs.hash(temp,context)!=digest:raise ValueError('Generated output changed before publication')
        self.fs.rename_noreplace(temp,destination)
        self._journal(op,'finalised',final_signature=signature(destination))
        self._journal(op,'completed',error=None)
        context.progress('Writing optional metadata',index+1,total,len(data),len(data))

    def _remove_created(self,op,context):
        self._safe_roots(op)
        source = Path(op.source)
        if signature(source)!=op.expected_signature or self.fs.hash(source,context)!=op.verification['sha256']:
            raise ValueError('Generated output changed; retain it')
        if context.cancelled():raise Cancelled()
        self._journal(op,'intent',remove_intent=True,error=None)
        self.fs.remove_source(source,op.expected_signature)
        self._journal(op,'completed',error=None)

    def _destination_matches(self,op,context=None):
        destination = Path(op.destination)
        details = op.verification
        if case_only_rename(op.source,op.destination) and not exact_name_exists(destination):
            return False
        if not destination.is_file() or destination.is_symlink() or not details.get('sha256'):
            return False
        observed = signature(destination)
        expected = details.get('final_signature') or (details.get('temp_signature') if details.get('mode') in ('copy','create') else op.expected_signature)
        if not expected or any(observed.get(key) != expected.get(key) for key in ('device','inode','size','mtime_ns')):
            return False
        return self.fs.hash(destination,context) == details['sha256']

    def _finish(self,op,context,index=0,total=1):
        context.progress('Verifying destination',index,total,int(op.expected_signature['size']),int(op.expected_signature['size']))
        self._safe_roots(op)
        if not self._destination_matches(op,context):
            raise ValueError('Published destination changed; preserve any source')
        source = Path(op.source)
        if op.verification.get('mode')=='case_rename':
            # On Windows the old spelling still resolves to the published file.
            # Never unlink that alias; an actual new old-spelling entry is retained.
            if exact_name_exists(source):
                raise ValueError('Source name reappeared; retain it for review')
        elif source.exists():
            if context.cancelled(): raise Cancelled()
            if signature(source) != op.expected_signature or self.fs.hash(source,context) != op.verification['sha256']:
                raise ValueError('Source changed; do not delete it')
            context.progress('Removing source',index,total,int(op.expected_signature['size']),int(op.expected_signature['size']))
            if context.cancelled(): raise Cancelled()
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
                    if op.kind=='remove_created' and op.state in ('intent','error','cancelled') and op.verification.get('remove_intent') and not Path(op.source).exists():
                        self._journal(op,'completed')
                        report.recovered_operation_ids.append(op.id)
                    elif self._destination_matches(op,context):
                        source = Path(op.source)
                        source_exists = exact_name_exists(source) if op.verification.get('mode')=='case_rename' else source.exists()
                        state = 'completed' if op.kind.startswith('create_') else 'finalised' if source_exists else 'completed'
                        self._journal(op,state,final_signature=signature(Path(op.destination)))
                        report.recovered_operation_ids.append(op.id)
                    elif op.verification.get('mode')=='case_rename' and op.verification.get('temp_path'):
                        temp = Path(op.verification['temp_path'])
                        expected_temp = Path(op.source).parent / ('.orion-' + op.id + '.part')
                        if temp!=expected_temp or not contained(temp,Path(op.verification['source_root'])):
                            raise ValueError('Case rename staging path escaped its recorded root')
                        if temp.exists() or temp.is_symlink():
                            if signature(temp)==op.expected_signature and self.fs.hash(temp,context)==op.verification['sha256']:
                                self._journal(op,'staged',temp_signature=signature(temp))
                                report.recovered_operation_ids.append(op.id)
                            else:
                                report.review_operation_ids.append(op.id)
                        elif exact_name_exists(Path(op.destination)) or not exact_name_exists(Path(op.source)):
                            report.review_operation_ids.append(op.id)
                    elif Path(op.destination).exists():
                        self._journal(op,'error',error='destination_identity_uncertain')
                        report.review_operation_ids.append(op.id)
                except (OSError,ValueError):
                    report.review_operation_ids.append(op.id)
            if plan_id is None:
                self._recover_completed_batches(report,context)
            return report

    def _recover_completed_batches(self,report,context):
        with self.store.transaction() as conn:
            batches=conn.execute("""SELECT b.* FROM orion_batches b WHERE b.state='running' OR EXISTS(
                SELECT 1 FROM orion_jobs j WHERE j.state='interrupted' AND j.kind IN ('organise','undo','sidecars')
                AND json_extract(j.payload,'$.plan_id')=b.plan_id)""").fetchall()
        for batch in batches:
            if context and context.cancelled():raise Cancelled()
            operations=self.operations(batch['plan_id'])
            if any(op.state!='completed' for op in operations):continue
            invalid=[]
            for op in operations:
                try:
                    self._safe_roots(op)
                    valid=not Path(op.source).exists() if op.kind=='remove_created' else self._destination_matches(op,context)
                    if not valid:invalid.append(op.id)
                except (OSError,ValueError):invalid.append(op.id)
            if invalid:
                report.review_operation_ids.extend(invalid)
                continue
            plan=self.planner.get(batch['plan_id'])
            result=self._complete_batch(plan,operations,batch['id'],[op.id for op in operations],[],[])
            with self.store.transaction() as conn:
                conn.execute("""UPDATE orion_jobs SET state=?,result=?,error=?,cancel=0,updated_at=? WHERE state='interrupted'
                    AND kind IN ('organise','undo','sidecars') AND json_extract(payload,'$.plan_id')=?""",
                    ('completed' if result.state=='completed' else 'failed',result.model_dump_json(),None if result.state=='completed' else result.state,utcnow(),plan.id))
            report.recovered_batch_ids.append(batch['id'])

    def _update_items_and_directories(self,operations):
        recovery_items = []
        by_item = {}
        for op in operations:
            if op.kind != 'move':continue
            by_item.setdefault(op.item_id,[]).append(op)
        for iid,group in by_item.items():
            if not all(op.state=='completed' for op in group): continue
            item = self.library.get(iid)
            organised_path = item.path
            destinations = [Path(op.destination) for op in group]
            directory = group[0].verification.get('source_directory')
            undo = group[0].verification.get('undo_of')
            residual_directory = False
            if directory:
                root = Path(directory)
                if root.is_dir():
                    for current,dirs,files in os.walk(root,topdown=False,followlinks=False):
                        try:
                            Path(current).rmdir()
                        except OSError:
                            pass
                    residual_directory = root.exists()
            if undo and (residual_directory or any(op.verification.get('partial_undo') for op in group)):
                # An item split across locations must not be advertised as restored.
                primary = next((op for op in group if op.source==item.path),None)
                if primary and not directory:item.path=primary.destination
                if residual_directory and not any(op.verification.get('partial_undo') for op in group):
                    item.path=group[0].verification['restore_item_path']
                if Path(item.path).exists():item.signature=signature(Path(item.path))
                item.metadata['recovery_note']='Undo left files in both locations; review the recovery paths before organising again.'
                item.metadata['recovery_paths']=list(dict.fromkeys([group[0].verification['restore_item_path'],str(directory) if directory else str(Path(organised_path).parent)]))
                recovery_items.append(iid)
                item.status='error'
                self.library.upsert(item)
                continue
            target = Path(group[0].verification['restore_item_path']) if undo else Path(group[0].verification.get('destination_item_path') or (os.path.commonpath([str(p.parent) for p in destinations]) if directory else destinations[0]))
            item.path = str(target)
            if target.exists():
                item.signature = signature(target)
            if undo:
                item.metadata.pop('recovery_note',None)
                item.metadata.pop('recovery_paths',None)
            item.status = ('approved' if item.decision else 'pending') if undo else 'organised'
            self.library.upsert(item)

        return recovery_items

    def _restore_conflicts(self,plan,operations):
        groups={}
        for op in operations:
            if op.kind=='move' and op.verification.get('source_directory'):
                groups.setdefault(op.item_id,[]).append(op)
        issues=[]
        for iid,group in groups.items():
            root=Path(group[0].verification['restore_item_path'])
            item=self.library.get(iid)
            with self.store.transaction() as conn:
                occupied=any(row['id']!=iid and normalized(row['path'])==normalized(root)
                    for row in conn.execute('SELECT id,path FROM orion_items WHERE source_id=?',(item.source_id,)))
                rows=conn.execute("SELECT data FROM orion_operations WHERE json_extract(data,'$.verification.undo_of')=? AND json_extract(data,'$.state')='completed' AND json_extract(data,'$.kind')='move'",(plan.undo_batch_id,)).fetchall()
            if occupied:
                issues.append(PlanIssue(code='restore_item_conflict',detail='Another indexed arrival occupies the original directory: '+str(root),item_id=iid,operation_id=group[0].id))
                continue
            if not root.exists():continue
            owned=set()
            for row in rows:
                done=Operation.model_validate_json(row['data'])
                destination=Path(done.destination)
                if done.item_id==iid and destination.is_relative_to(root):
                    try:
                        self._safe_roots(done)
                        if self._destination_matches(done):
                            owned.add(normalized(destination))
                            owned.update(normalized(parent) for parent in destination.parents if parent.is_relative_to(root))
                    except (OSError,ValueError):pass
            unexpected=not root.is_dir() or not contained(root,Path(group[0].verification['destination_root']))
            if not unexpected:
                walk_errors=[]
                for directory,dirs,files in os.walk(root,followlinks=False,onerror=walk_errors.append):
                    if any(normalized(Path(directory)/name) not in owned for name in [*dirs,*files]):
                        unexpected=True
                        break
                unexpected=unexpected or bool(walk_errors)
            if unexpected:
                issues.append(PlanIssue(code='restore_directory_populated',detail='Keep the new arrival unchanged; the original directory contains unexpected members: '+str(root),item_id=iid,operation_id=group[0].id))
        return issues

    def undo_plan(self,batch_id,exclude_operation_ids=None) -> OperationPlan:
        with self.store.transaction() as conn:
            row = conn.execute('SELECT plan_id FROM orion_batches WHERE id=?',(batch_id,)).fetchone()
        if not row:
            raise KeyError('Batch not found')
        originals = self.operations(row['plan_id'])
        excluded=list(dict.fromkeys(exclude_operation_ids or []))
        eligible={op.id for op in originals if op.state=='completed' and op.kind in ('move','create_nfo','create_artwork')}
        if not set(excluded).issubset(eligible):raise ValueError('Excluded operation is not a completed member of this batch')
        partial_items={op.item_id for op in originals if op.id in excluded and op.kind=='move'}
        plan = OperationPlan(id=str(uuid4()),undo_batch_id=batch_id,undo_operation_states={op.id:op.state for op in originals},excluded_operation_ids=excluded)
        for op in originals:
            if op.state != 'completed': continue
            if op.id in excluded:
                plan.warnings.append(PlanIssue(code='undo_member_excluded',detail='Leave this file unchanged: '+op.destination,item_id=op.item_id,operation_id=op.id))
                continue
            source,destination = Path(op.destination),Path(op.source)
            details = op.verification
            if op.kind.startswith('create_'):
                if op.item_id in partial_items:
                    plan.warnings.append(PlanIssue(code='sidecar_retained_for_excluded_media',detail='Retain generated metadata for media left organised: '+str(source),item_id=op.item_id,operation_id=op.id))
                    continue
                if not self._destination_matches(op):
                    plan.warnings.append(PlanIssue(code='sidecar_changed',detail='Generated sidecar changed or disappeared; retain it: '+str(source),item_id=op.item_id))
                    continue
                item = self.library.get(op.item_id)
                inverse = Operation(id=str(uuid4()),plan_id=plan.id,item_id=op.item_id,kind='remove_created',source=str(source),destination=str(source),expected_signature=details['final_signature'],verification={
                    'source_root':details['destination_root'],'destination_root':details['destination_root'],'source_root_resolved':details['destination_root_resolved'],'destination_root_resolved':details['destination_root_resolved'],
                    'item_path':str(source),'item_signature':details['final_signature'],'item_decision':item.decision.model_dump() if item.decision else None,
                    'sha256':details['sha256'],'undo_of':batch_id,'transfer_mode':'remove'})
                plan.operations.insert(0,inverse)
                continue
            if op.kind!='move':continue
            if not self._destination_matches(op):
                plan.issues.append(PlanIssue(code='target_changed',detail='Organised file changed; retain it: '+str(source),item_id=op.item_id,operation_id=op.id))
                continue
            item = self.library.get(op.item_id)
            inverse = Operation(id=str(uuid4()),plan_id=plan.id,item_id=op.item_id,source=str(source),destination=str(destination),expected_signature=details['final_signature'],
                                verification={'source_root':details['destination_root'],'destination_root':details['source_root'],
                                              'source_root_resolved':details['destination_root_resolved'],'destination_root_resolved':details['source_root_resolved'],
                                              'item_path':str(source),'item_signature':details['final_signature'],'item_decision':item.decision.model_dump() if item.decision else None,
                                              'source_directory':str(item.path) if details.get('source_directory') else '',
                                              'undo_of':batch_id,'restore_item_path':details['item_path'],'original_operation_id':op.id,'partial_undo':op.item_id in partial_items})
            plan.operations.append(inverse)
        plan.issues.extend(self._restore_conflicts(plan,plan.operations))
        checked=self.planner._validate(plan)
        originals_by_inverse={op.id:op.verification.get('original_operation_id',op.id) for op in checked.operations}
        for issue in checked.issues:
            issue.operation_id=originals_by_inverse.get(issue.operation_id,issue.operation_id)
        return self.planner.save(checked)
