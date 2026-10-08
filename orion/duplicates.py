"""Read-only comparison; exact item content is distinct from title/edition evidence."""
import hashlib,json,re
from pathlib import Path
from collections import defaultdict
from pydantic import Field
from orion.models import Record,MediaItem
from orion.discovery import signature,Cancelled
from orion.filesystem import Filesystem
from orion.planner import contained

class ComparedItem(Record):
    item_id:str
    path:str
    kind:str
    title:str
    bytes:int
    provider:str=''
    provider_id:str=''
    quality:dict=Field(default_factory=dict)
    edition:str=''
    sha256:str|None=None

class VersionGroup(Record):
    item_ids:list[str]
    evidence:list[str]

class Comparison(Record):
    exact:bool
    items:list[ComparedItem]=Field(default_factory=list)
    exact_groups:list[list[str]]=Field(default_factory=list)
    version_groups:list[VersionGroup]=Field(default_factory=list)
    errors:list[dict]=Field(default_factory=list)

class Duplicates:
    def __init__(self,library):
        self.library,self.fs=library,Filesystem()

    @staticmethod
    def _identity(item,metadata):
        decision=item.decision
        if decision and decision.provider_id:return (item.kind,decision.provider,decision.provider_id),'Confirmed provider identifier agrees'
        normal=lambda value:re.sub(r'\W+',' ',str(value).casefold()).strip()
        title=normal(metadata.get('title',''))
        if not title:return None,''
        creator=normal(metadata.get('artist' if item.kind=='music' else 'author','')) if item.kind in ('music','books') else str(metadata.get('year',''))
        return (item.kind,title,creator),'Title and available creator/year metadata agree; editions may differ'

    def _hash(self,path,sig,context):
        if sig['type']=='file':return self.fs.hash(path,context)
        # Whole folder content, including associated files; names do not affect content equality.
        members=[]
        for relative,child in sig['children'].items():
            if context.cancelled():raise Cancelled()
            members.append((child['size'],self.fs.hash(path/relative,context)))
        return hashlib.sha256(json.dumps(sorted(members),separators=(',',':')).encode()).hexdigest()

    def compare(self,item_ids,exact,context):
        ids=list(dict.fromkeys(item_ids))
        if not 2<=len(ids)<=500:raise ValueError('Select between 2 and 500 items to compare')
        result=Comparison(exact=exact)
        versions,hashes=defaultdict(list),defaultdict(list)
        roots=[Path(s['path']) for s in self.library.sources()]
        with self.library.store.transaction() as conn:
            roots.extend(Path(row[0]) for row in conn.execute('SELECT path FROM orion_destinations'))
        for index,iid in enumerate(ids):
            if context.cancelled():raise Cancelled()
            item=self.library.get(iid)
            path=Path(item.path)
            metadata={**item.metadata,**(item.decision.metadata if item.decision else {})}
            try:
                if not any(contained(path,root) for root in roots):raise ValueError('outside_root')
                before=signature(path,context)
                if item.signature and before!=item.signature:raise ValueError('source_changed')
                digest=self._hash(path,before,context) if exact else None
                if signature(path,context)!=before:raise ValueError('source_changed')
                compared=ComparedItem(item_id=iid,path=str(path),kind=item.kind,title=str(metadata.get('title',path.name)),
                    bytes=before.get('size',sum(c.get('size',0) for c in before.get('children',{}).values())),
                    provider=item.decision.provider if item.decision else '',provider_id=item.decision.provider_id if item.decision else '',
                    quality=metadata.get('quality',{}) if isinstance(metadata.get('quality'),dict) else {},edition=str(metadata.get('edition','')),sha256=digest)
                result.items.append(compared)
                if digest:hashes[digest].append(iid)
                identity,evidence=self._identity(item,metadata)
                if identity:versions[(identity,evidence)].append(iid)
            except Cancelled:raise
            except (OSError,ValueError) as exc:
                code=str(exc) if isinstance(exc,ValueError) and str(exc) in ('source_changed','outside_root') else 'source_unavailable'
                result.errors.append({'item_id':iid,'code':code})
            context.progress('Comparing exact content' if exact else 'Comparing metadata',index+1,len(ids))
        result.exact_groups=[ids for ids in hashes.values() if len(ids)>1]
        result.version_groups=[VersionGroup(item_ids=ids,evidence=[evidence]) for (identity,evidence),ids in versions.items() if len(ids)>1]
        return result
