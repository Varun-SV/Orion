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
        if not path.is_dir() or path.is_symlink() or getattr(path,'is_junction',lambda:False)():
            raise ValueError('Choose an accessible folder, not a link')
        for source in self.sources():
            a,b = normalized(source['path']),normalized(path)
            if a == b or a.startswith(b + __import__('os').sep) or b.startswith(a + __import__('os').sep):
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
            row=conn.execute('SELECT * FROM orion_items WHERE id=?',(item.id,)).fetchone()
            if row:
                latest=self.from_row(row)
                if latest.path != item.path:
                    return latest  # A completed organisation already moved this item.
                if latest.signature == item.signature or not latest.signature:
                    item=item.model_copy(update={'decision':latest.decision,
                        'status':('approved' if latest.decision else 'pending') if latest.status=='unavailable' else latest.status,
                        'metadata':{**latest.metadata,**item.metadata}})
                else:
                    item=item.model_copy(update={'decision':None,'status':'pending'})
            conn.execute('INSERT INTO orion_items VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET path=excluded.path,kind=excluded.kind,status=excluded.status,signature=excluded.signature,metadata=excluded.metadata,decision=excluded.decision,updated_at=excluded.updated_at',
                (item.id,item.source_id,item.path,item.kind,item.status,json.dumps(item.signature),json.dumps(safe_metadata(item.metadata)),item.decision.model_dump_json() if item.decision else None,utcnow()))
        return item

    def decide(self, item_id: str, decision: MatchDecision) -> MediaItem:
        if decision.item_id != item_id or not str(decision.metadata.get('title','')).strip():
            raise ValueError('Decision must identify this item and supply a title')
        decision = decision.model_copy(update={'metadata':safe_metadata(decision.metadata)})
        with self.store.transaction() as conn:
            changed=conn.execute("UPDATE orion_items SET decision=?,status='approved',updated_at=? WHERE id=?",(decision.model_dump_json(),utcnow(),item_id)).rowcount
            if not changed:raise KeyError('Item not found')
        return self.get(item_id)

    def clear_decision(self,item_id):
        with self.store.transaction() as conn:
            changed=conn.execute("UPDATE orion_items SET decision=NULL,status='pending',updated_at=? WHERE id=?",(utcnow(),item_id)).rowcount
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

    def status(self, item_id, status):
        if status not in ('pending','approved','organised','error','unavailable','no_match'):raise ValueError('Unknown item state')
        with self.store.transaction() as conn:
            changed=conn.execute('UPDATE orion_items SET status=?,updated_at=? WHERE id=?',(status,utcnow(),item_id)).rowcount
            if not changed:raise KeyError('Item not found')
        return self.get(item_id)
