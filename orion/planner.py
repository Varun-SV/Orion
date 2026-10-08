from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
from typing import Literal
from uuid import uuid4
from pydantic import Field
from orion.models import Record,MediaItem,MatchDecision,Operation,OperationPlan,PlanIssue
from orion.naming import Naming,NamingProfile,valid_relative
from orion.discovery import signature,linked,VIDEO,parsed_metadata
from orion.store import normalized,utcnow

class PlanOptions(Record):
    destination_id: str | None = None
    in_place: bool = False
    conflict: Literal['block','skip','keep_both'] = 'block'
    profile: NamingProfile = Field(default_factory=NamingProfile)


def nearest_existing(path):
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    return path

def contained(path,root):
    path,root = Path(path).absolute(),Path(root).absolute()
    if not path.is_relative_to(root) or not path.resolve().is_relative_to(root.resolve()):
        return False
    cursor = path
    while cursor != root.parent:
        if linked(cursor):
            return False
        if cursor == root:
            break
        cursor = cursor.parent
    return True

class Planner:
    def __init__(self,library):
        self.library = library
        self.store = library.store

    def get(self,plan_id):
        with self.store.transaction() as conn:
            row = conn.execute('SELECT data FROM orion_plans WHERE id=?',(plan_id,)).fetchone()
        if not row:
            raise KeyError('Plan not found')
        return OperationPlan.model_validate_json(row['data'])

    def save(self,plan):
        with self.store.transaction() as conn:
            conn.execute('INSERT INTO orion_plans VALUES(?,?,?,?)',(plan.id,plan.revision,plan.model_dump_json(),utcnow()))
            for operation in plan.operations:
                conn.execute('INSERT INTO orion_operations VALUES(?,?,?,?)',(operation.id,plan.id,operation.model_dump_json(),utcnow()))
        return plan

    def create(self,item_ids:list[str],options:PlanOptions) -> OperationPlan:
        if not item_ids or len(item_ids)>500:
            raise ValueError('Select between 1 and 500 items')
        plan = OperationPlan(id=str(uuid4()))
        sources = {r['id']:r for r in self.library.sources()}
        with self.store.transaction() as conn:
            destinations = {r['id']:dict(r) for r in conn.execute('SELECT * FROM orion_destinations')}
            categories = {r['kind']:dict(r) for r in conn.execute('SELECT * FROM orion_categories')}
        if not options.in_place and options.destination_id not in destinations:
            raise ValueError('Select a configured destination')
        reserved = set()
        reserved_folders = set()
        def issue(code,detail,item_id='',operation_id=''):
            plan.issues.append(PlanIssue(code=code,detail=detail,item_id=item_id,operation_id=operation_id))
        for iid in dict.fromkeys(item_ids):
            item = self.library.get(iid)
            if not item.decision or item.status not in ('approved','error'):
                issue('review_required','Confirm the item before organisation',iid)
                continue
            source = Path(item.path)
            source_root = Path(sources[item.source_id]['path'])
            destination_root = source_root if options.in_place else Path(destinations[options.destination_id]['path'])
            if not destination_root.is_dir() or linked(destination_root):
                issue('destination_unavailable','Reconnect the selected destination folder',iid)
                continue
            if not options.in_place and any(destination_root.is_relative_to(Path(s['path'])) or Path(s['path']).is_relative_to(destination_root) for s in sources.values()):
                issue('roots_overlap','Source and destination roots cannot overlap',iid)
                continue
            if not contained(source,source_root):
                issue('outside_source','Item is outside its configured source or contains a link',iid)
                continue
            try:
                current = signature(source)
            except (OSError,ValueError):
                issue('source_unavailable','Source is unavailable or linked',iid)
                continue
            if item.signature and current != item.signature:
                issue('source_changed','Rescan and review changed media',iid)
                continue
            if not item.signature:
                item.signature = current
            try:
                category_path = valid_relative(categories.get(item.kind,{}).get('dest_subpath') or item.kind)
                base = destination_root if options.in_place else destination_root/category_path
                pairs = self._layout(item,options,base,reserved_folders)
            except FileExistsError:
                issue('destination_exists','Directory already exists; choose a separate version or skip',iid)
                continue
            except (ValueError,OSError) as exc:
                issue('invalid_layout',str(exc),iid)
                continue
            for src,dst,expected in pairs:
                if normalized(src) == normalized(dst):
                    continue
                if options.conflict == 'skip' and (dst.exists() or normalized(dst) in reserved):
                    continue
                if options.conflict == 'keep_both':
                    original = dst
                    version = 2
                    while dst.exists() or normalized(dst) in reserved:
                        dst = original.with_name(f'{original.stem} ({version}){original.suffix}')
                        version += 1
                operation = Operation(id=str(uuid4()),plan_id=plan.id,item_id=iid,source=str(src),destination=str(dst),expected_signature=expected,
                                      verification={'source_root':str(source_root),'destination_root':str(destination_root),
                                                    'source_root_resolved':str(source_root.resolve()),'destination_root_resolved':str(destination_root.resolve()),
                                                    'item_signature':current,'item_decision':item.decision.model_dump(),'item_path':item.path,'source_directory':item.path if current['type']=='directory' else '',
                                                    'profile_id':options.profile.id})
                if normalized(dst) in reserved:
                    issue('duplicate_destination','Two operations target the same path',iid,operation.id)
                reserved.add(normalized(dst))
                plan.operations.append(operation)
        checked = self._validate(plan)
        return self.save(checked)

    def _layout(self,item,options,base,reserved_folders):
        source = Path(item.path)
        if item.signature['type'] == 'file':
            layout = Naming.render(item,options.profile).path
            target = source.parent/Path(layout).name if options.in_place else base/layout
            return [(source,target,item.signature)]
        folder = Naming.render(item,options.profile).path
        folder_target = source.parent/folder if options.in_place else base/folder
        if normalized(folder_target) != normalized(source):
            if options.conflict == 'keep_both':
                original_folder = folder_target
                version = 2
                while folder_target.exists() or normalized(folder_target) in reserved_folders:
                    folder_target = original_folder.with_name(f'{original_folder.name} ({version})')
                    version += 1
            elif folder_target.exists() or normalized(folder_target) in reserved_folders:
                if options.conflict == 'skip':
                    return []
                raise FileExistsError('Directory already exists')
        reserved_folders.add(normalized(folder_target))
        children = item.signature['children']
        mappings = {}
        for relative,expected in children.items():
            file = source/relative
            if file.suffix.lower() in VIDEO:
                parsed = parsed_metadata(file,item.kind)
                metadata = {**parsed,**item.decision.metadata}
                # Confirmed series identity remains, individual episode numbers/quality come from each file.
                for key in ('season','episode','quality'):
                    if key in parsed:
                        metadata[key] = parsed[key]
                child = item.model_copy(update={'path':str(file),'signature':expected,'metadata':metadata,
                                                'decision':MatchDecision(item_id=item.id,provider=item.decision.provider,provider_id=item.decision.provider_id,metadata=metadata,evidence=item.decision.evidence)})
                rendered = Path(Naming.render(child,options.profile).path)
                target = folder_target/file.relative_to(source).parent/rendered.name if item.kind in ('movies','anime_films') else folder_target.joinpath(*(rendered.parts[1:] if len(rendered.parts)>1 else (rendered.name,)))
                mappings[relative] = target
        result = []
        for relative,expected in children.items():
            file = source/relative
            target = mappings.get(relative)
            if target is None:
                candidates = sorted([(str(Path(video).with_suffix('')),dst) for video,dst in mappings.items()],key=lambda r:len(r[0]),reverse=True)
                for stem,dst in candidates:
                    if str(Path(relative)).startswith(stem+'.'):
                        suffix = str(Path(relative))[len(stem):]
                        target = dst.with_name(dst.stem+suffix)
                        break
                target = target or folder_target/relative
            result.append((file,target,expected))
        return result

    def validate(self,plan_id:str,revision:int) -> OperationPlan:
        plan = self.get(plan_id)
        if revision != plan.revision:
            raise ValueError('Plan revision is stale')
        return self._validate(plan)

    def _validate(self,plan):
        checked = plan.model_copy(deep=True)
        issues = list(checked.issues)
        required_space = {}
        checked_items = set()
        for op in checked.operations:
            src,dst = Path(op.source),Path(op.destination)
            details = op.verification
            def issue(code,detail):
                issues.append(PlanIssue(code=code,detail=detail,item_id=op.item_id,operation_id=op.id))
            srcroot,dstroot = Path(details['source_root']),Path(details['destination_root'])
            if not srcroot.is_dir() or not dstroot.is_dir():
                issue('destination_unavailable','Reconnect source/destination roots')
                continue
            if str(srcroot.resolve()) != details['source_root_resolved'] or str(dstroot.resolve()) != details['destination_root_resolved'] or not contained(src,srcroot) or not contained(dst,dstroot):
                issue('outside_root','A path escaped the selected roots or became linked')
                continue
            if op.item_id not in checked_items:
                current_item = self.library.get(op.item_id)
                current_decision = current_item.decision.model_dump() if current_item.decision else None
                if current_decision != details.get('item_decision'):
                    issue('decision_changed','Metadata approval changed; create a new preview')
                try:
                    if signature(Path(details['item_path'])) != details['item_signature']:
                        issue('source_changed','Source signature changed after preview')
                except (OSError,ValueError):
                    issue('source_unavailable','Source is unavailable')
                checked_items.add(op.item_id)
            try:
                if signature(src) != op.expected_signature:
                    issue('source_changed','Source file changed after preview')
            except (OSError,ValueError):
                issue('source_unavailable','Source file is unavailable')
            if dst.exists() or dst.is_symlink():
                issue('destination_exists','Keep the existing file or select a different layout')
            ancestor = nearest_existing(dst.parent)
            if not ancestor.is_dir() or not os.access(ancestor,os.W_OK):
                issue('destination_access','Destination parent is not writable')
                continue
            try:
                device = ancestor.stat().st_dev
                if src.exists() and src.stat().st_dev != device:
                    prior = required_space.get(device,(ancestor,0))
                    required_space[device] = (ancestor,prior[1]+int(op.expected_signature.get('size',0)))
            except OSError:
                issue('destination_unavailable','Cannot inspect destination volume')
        for ancestor,required in required_space.values():
            if shutil.disk_usage(ancestor).free < required:
                issues.append(PlanIssue(code='insufficient_space',detail=f'{required} bytes required on {ancestor}'))
        seen = set()
        checked.issues = [i for i in issues if not ((i.code,i.item_id,i.operation_id) in seen or seen.add((i.code,i.item_id,i.operation_id)))]
        return checked
