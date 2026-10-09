from __future__ import annotations
import json
from pathlib import Path
from uuid import uuid4
from orion.models import MediaItem, MatchDecision, Page, KINDS
from orion.store import Store, item_id, normalized, safe_metadata, utcnow

class Library:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def from_row(row):
        if row is None:
            raise KeyError('Item not found')
        values = dict(row)
        values.pop('updated_at', None)
        for key in ('signature','metadata','decision'):
            values[key] = json.loads(values[key]) if values[key] else None
        return MediaItem.model_validate(values)

    def get(self, item_id: str) -> MediaItem:
        with self.store.transaction() as conn:
            return self.from_row(conn.execute('SELECT * FROM orion_items WHERE id=?', (item_id,)).fetchone())

    def at_path(self, source_id: str, path: str) -> MediaItem:
        with self.store.transaction() as conn:
            return self.from_row(conn.execute('SELECT * FROM orion_items WHERE source_id=? AND path=?', (source_id,str(path))).fetchone())

    def query(self, query='', kind=None, status=None, offset=0, limit=100) -> Page[MediaItem]:
        if offset < 0 or not 1 <= limit <= 500:
            raise ValueError('Invalid pagination')
        clauses, params = [], []
        if kind:
            if kind not in KINDS:
                raise ValueError('Unknown collection')
            clauses.append('kind=?')
            params.append(kind)
        if status == 'review':
            clauses.append("status IN ('pending','error','no_match')")
        elif status:
            clauses.append('status=?')
            params.append(status)
        if query:
            clauses.append("(path LIKE ? ESCAPE '!' OR metadata LIKE ? ESCAPE '!' OR decision LIKE ? ESCAPE '!')")
            pattern = '%' + query.replace('!','!!').replace('%','!%').replace('_','!_') + '%'
            params.extend([pattern]*3)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        with self.store.transaction() as conn:
            total = conn.execute('SELECT COUNT(*) FROM orion_items' + where, params).fetchone()[0]
            rows = conn.execute('SELECT * FROM orion_items' + where + ' ORDER BY path COLLATE NOCASE,id LIMIT ? OFFSET ?', [*params,limit,offset]).fetchall()
        return Page(items=[self.from_row(r) for r in rows],total=total,offset=offset,limit=limit)

    def sources(self):
        with self.store.transaction() as conn:
            return [dict(r) for r in conn.execute('SELECT * FROM orion_sources ORDER BY label')]

    def add_source(self, path: Path, label='', kind='auto'):
        path = Path(path).absolute()
        if kind != 'auto' and kind not in KINDS:
            raise ValueError('Unknown collection')
        from orion.discovery import linked
        if not path.is_dir() or any(linked(parent) for parent in (path,*path.parents)):
            raise ValueError('Choose an accessible folder, not a link')
        for source in self.sources():
            a,b = normalized(source['path']),normalized(path)
            if Path(a).is_relative_to(Path(b)) or Path(b).is_relative_to(Path(a)):
                raise ValueError('Source folders cannot overlap')
        sid = item_id('source', path)
        with self.store.transaction() as conn:
            conn.execute('INSERT INTO orion_sources(id,path,label,kind) VALUES(?,?,?,?)',(sid,str(path),label.strip() or path.name,kind))
        return next(r for r in self.sources() if r['id']==sid)

    def upsert(self, item: MediaItem):
        with self.store.transaction() as conn:
            conn.execute('INSERT INTO orion_items VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET path=excluded.path,kind=excluded.kind,status=excluded.status,signature=excluded.signature,metadata=excluded.metadata,decision=excluded.decision,updated_at=excluded.updated_at',
                         (item.id,item.source_id,item.path,item.kind,item.status,json.dumps(item.signature),json.dumps(safe_metadata(item.metadata)),item.decision.model_dump_json() if item.decision else None,utcnow()))
        return item

    def discovered(self,item):
        """Merge an observed signature without replacing a concurrent confirmation."""
        with self.store.transaction() as conn:
            row=conn.execute('SELECT * FROM orion_items WHERE source_id=? AND path=?',(item.source_id,item.path)).fetchone()
            if row is None:
                retired=conn.execute('SELECT * FROM orion_items WHERE id=?',(item.id,)).fetchone()
                if retired:
                    # A path is a location, not a permanent identity. Distinguish
                    # a real new arrival from a scan racing a completed move.
                    from orion.discovery import signature
                    if signature(Path(item.path)) != item.signature:
                        raise ValueError('Observed source changed during discovery')
                    item=item.model_copy(update={'id':str(uuid4()),'decision':None,'status':'pending'})
            if row:
                latest=self.from_row(row)
                if self._has_unfinished_operations(conn,latest.id):
                    return latest
                item=item.model_copy(update={'id':latest.id})
                if latest.signature == item.signature or not latest.signature:
                    item=item.model_copy(update={'decision':latest.decision,
                        'status':('approved' if latest.decision else 'pending') if latest.status=='unavailable' else latest.status,
                        'metadata':{**latest.metadata,**item.metadata}})
                else:
                    item=item.model_copy(update={'decision':None,'status':'pending'})
            conn.execute('INSERT INTO orion_items VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET path=excluded.path,kind=excluded.kind,status=excluded.status,signature=excluded.signature,metadata=excluded.metadata,decision=excluded.decision,updated_at=excluded.updated_at',
                (item.id,item.source_id,item.path,item.kind,item.status,json.dumps(item.signature),json.dumps(safe_metadata(item.metadata)),item.decision.model_dump_json() if item.decision else None,utcnow()))
        return item

    def _has_unfinished_operations(self,conn,item_id):
        # A stopped batch still owns intermediate filesystem observations.
        # A successful full undo releases that ownership for future arrivals.
        return conn.execute("""SELECT 1 FROM orion_batches b
            JOIN orion_operations o ON o.plan_id=b.plan_id
            WHERE json_extract(o.data,'$.item_id')=? AND json_extract(o.data,'$.state')!='completed'
            AND EXISTS(SELECT 1 FROM orion_operations moved WHERE moved.plan_id=b.plan_id
                AND json_extract(moved.data,'$.item_id')=json_extract(o.data,'$.item_id')
                AND json_extract(moved.data,'$.kind')='move'
                AND (json_extract(moved.data,'$.state')='completed'
                    OR json_extract(moved.data,'$.verification.final_signature') IS NOT NULL
                    OR (json_extract(moved.data,'$.verification.mode')='case_rename'
                        AND json_extract(moved.data,'$.verification.temp_signature') IS NOT NULL)))
            AND NOT EXISTS(SELECT 1 FROM orion_batches restored JOIN orion_plans p ON p.id=restored.plan_id
                WHERE restored.state='completed' AND json_extract(p.data,'$.undo_batch_id')=b.id)
            LIMIT 1""",(item_id,)).fetchone() is not None

    def _ensure_decision_editable(self,conn,item_id):
        active=conn.execute("SELECT kind,payload FROM orion_jobs WHERE state IN ('running','cancelling') AND kind IN ('organise','undo','sidecars','recovery')").fetchall()
        plans={json.loads(row['payload']).get('plan_id') for row in active if row['kind']!='recovery'}
        if any(row['kind']=='recovery' for row in active):
            plans.update(row[0] for row in conn.execute("SELECT plan_id FROM orion_batches WHERE state='running'"))
            plans.update(json.loads(row[0]).get('plan_id') for row in conn.execute("SELECT payload FROM orion_jobs WHERE state='interrupted' AND kind IN ('organise','undo','sidecars')"))
        plans.discard(None)
        for plan_id in plans:
            if conn.execute("SELECT 1 FROM orion_operations WHERE plan_id=? AND json_extract(data,'$.item_id')=? LIMIT 1",(plan_id,item_id)).fetchone():
                raise ValueError('This item has an active filesystem job; wait for execution to finish before changing its decision')

    def decide(self, item_id: str, decision: MatchDecision) -> MediaItem:
        if decision.item_id != item_id or not str(decision.metadata.get('title','')).strip():
            raise ValueError('Decision must identify this item and supply a title')
        decision = decision.model_copy(update={'metadata':safe_metadata(decision.metadata)})
        with self.store.transaction() as conn:
            self._ensure_decision_editable(conn,item_id)
            changed=conn.execute("UPDATE orion_items SET decision=?,status=CASE WHEN status='organised' THEN status ELSE 'approved' END,updated_at=? WHERE id=?",(decision.model_dump_json(),utcnow(),item_id)).rowcount
            if not changed:raise KeyError('Item not found')
        return self.get(item_id)

    def clear_decision(self,item_id):
        with self.store.transaction() as conn:
            self._ensure_decision_editable(conn,item_id)
            changed=conn.execute("UPDATE orion_items SET decision=NULL,status=CASE WHEN status='organised' THEN status ELSE 'pending' END,updated_at=? WHERE id=?",(utcnow(),item_id)).rowcount
            if not changed:raise KeyError('Item not found')
        return self.get(item_id)

    def annotate(self, item_id, **metadata):
        updates=safe_metadata(metadata)
        with self.store.transaction() as conn:
            row=conn.execute('SELECT metadata FROM orion_items WHERE id=?',(item_id,)).fetchone()
            if not row:raise KeyError('Item not found')
            current=json.loads(row[0]);current.update(updates)
            conn.execute('UPDATE orion_items SET metadata=?,updated_at=? WHERE id=?',(json.dumps(current),utcnow(),item_id))
        return self.get(item_id)

    def publish_lookup(self,item_id,observed_signature,candidates):
        # The signature and current decision are read with the same writer
        # transaction that publishes candidates and their resulting status.
        updates=safe_metadata({'candidates':candidates,'lookup_state':'ready' if candidates else 'no_match','lookup_error':None})
        with self.store.transaction() as conn:
            latest=self.from_row(conn.execute('SELECT * FROM orion_items WHERE id=?',(item_id,)).fetchone())
            if latest.signature!=observed_signature:
                return False
            metadata={**latest.metadata,**updates}
            conn.execute("UPDATE orion_items SET metadata=?,status=CASE WHEN decision IS NULL AND ?=0 THEN 'no_match' ELSE status END,updated_at=? WHERE id=?",
                         (json.dumps(metadata),len(candidates),utcnow(),item_id))
        return True

    def lookup_failed(self, item_id, observed_signature, code):
        # Read and update under one writer transaction: confirmation/organisation
        # may have completed while a bounded provider request was in flight.
        with self.store.transaction() as conn:
            row=conn.execute('SELECT * FROM orion_items WHERE id=?',(item_id,)).fetchone()
            latest=self.from_row(row)
            if latest.signature != observed_signature:
                return latest
            metadata={**latest.metadata,'lookup_state':'error','lookup_error':code}
            conn.execute("UPDATE orion_items SET metadata=?,status=CASE WHEN decision IS NULL THEN 'error' ELSE status END,updated_at=? WHERE id=?",
                         (json.dumps(safe_metadata(metadata)),utcnow(),item_id))
        return self.get(item_id)

    def status(self, item_id, status):
        if status not in ('pending','approved','organised','error','unavailable','no_match'):raise ValueError('Unknown item state')
        with self.store.transaction() as conn:
            changed=conn.execute('UPDATE orion_items SET status=?,updated_at=? WHERE id=?',(status,utcnow(),item_id)).rowcount
            if not changed:raise KeyError('Item not found')
        return self.get(item_id)
