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
    profile_id: str | None = None
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
        self.catalogue = None

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
        if options.profile_id:
            from orion.profiles import Profiles
            options = options.model_copy(update={'profile':Profiles(self.library).get(options.profile_id)})
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
            if options.in_place and item.kind not in ('music','books'):
                issue('invalid_layout','In-place renaming is available for music and books',iid)
                continue
            from orion.profiles import Profiles
            profile = options.profile if options.profile_id or options.profile != NamingProfile() else Profiles(self.library).get('default-'+item.kind)
            item_options = options.model_copy(update={'profile':profile})
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
                pairs, item_target = self._layout(item,item_options,base,reserved_folders,reserved)
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
                operation = Operation(id=str(uuid4()),plan_id=plan.id,item_id=iid,source=str(src),destination=str(dst),expected_signature=expected,
                                      verification={'source_root':str(source_root),'destination_root':str(destination_root),
                                                    'source_root_resolved':str(source_root.resolve()),'destination_root_resolved':str(destination_root.resolve()),
                                                    'item_signature':current,'item_decision':item.decision.model_dump(),'item_path':item.path,'source_directory':item.path if current['type']=='directory' else '',
                                                    'destination_item_path':str(item_target),'profile_id':profile.id,'profile_version':profile.version,'profile_snapshot':profile.model_dump()})
                if normalized(dst) in reserved:
                    issue('duplicate_destination','Two operations target the same path',iid,operation.id)
                reserved.add(normalized(dst))
                plan.operations.append(operation)
            self._sidecars(plan,item,item_options,base,item_target,pairs,source_root,destination_root,reserved)
        checked = self._validate(plan)
        return self.save(checked)

    def _layout(self,item,options,base,reserved_folders,reserved=None):
        source = Path(item.path)
        if item.signature['type'] == 'file':
            layout = Naming.render(item,options.profile).path
            target = source.parent/Path(layout).name if options.in_place else base/layout
            companions = [p for p in source.parent.iterdir() if p != source and p.name.startswith(source.stem+'.') and p.suffix.lower() in ('.srt','.ass','.ssa','.sub','.idx','.vtt','.nfo','.jpg','.jpeg','.png','.webp') and p.is_file() and not linked(p)]
            original = target
            version = 2
            def members(candidate):
                return [(source,candidate,item.signature), *[(p,candidate.with_name(candidate.stem+p.name[len(source.stem):]),signature(p)) for p in companions]]
            pairs = members(target)
            if options.conflict == 'keep_both':
                while any(normalized(src)!=normalized(dst) and (dst.exists() or normalized(dst) in (reserved or set())) for src,dst,_ in pairs):
                    target = original.with_name(f'{original.stem} ({version}){original.suffix}')
                    version += 1
                    pairs = members(target)
            return pairs,target
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
                    return [],folder_target
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
        return result,folder_target

    def _sidecars(self,plan,item,options,base,item_target,pairs,source_root,destination_root,reserved):
        from orion.integrations.sidecars import Sidecars
        specs = Sidecars.plan(item,options.profile)
        rendered = Path(Naming.render(item,options.profile).path)
        directory = item.signature['type']=='directory'
        actual = Path(item_target)
        def project(relative):
            relative = Path(relative)
            if directory:
                return actual/relative.relative_to(rendered)
            parent = actual.parent
            if relative.parent == rendered.parent:
                name = relative.name
                if name.startswith(rendered.stem+'.'):
                    name = actual.stem+name[len(rendered.stem):]
                return parent/name
            if rendered.parent.is_relative_to(relative.parent):
                for _ in rendered.parent.relative_to(relative.parent).parts:
                    parent = parent.parent
                return parent/relative.name
            raise ValueError('Sidecar layout does not share the selected media folder')
        projected = []
        for spec in specs:
            if spec.warning:
                plan.warnings.append(PlanIssue(code='optional_output_unavailable',detail=spec.warning,item_id=item.id))
                continue
            try:
                projected.append((spec,project(spec.path)))
            except ValueError:
                plan.warnings.append(PlanIssue(code='sidecar_layout',detail='This layout has no separate folder for the optional sidecar',item_id=item.id))
        if options.profile.episode_nfo_enabled and item.kind in ('series','anime','web_series'):
            catalogue = {}
            seasons = set()
            for src,dst,expected in pairs:
                if src.suffix.lower() not in VIDEO: continue
                metadata = parsed_metadata(src,item.kind)
                season,episode = metadata.get('season',1),metadata.get('episode',1)
                if self.catalogue and item.decision.provider=='tmdb' and item.decision.provider_id and season not in seasons:
                    seasons.add(season)
                    class Context:
                        def cancelled(self):return False
                        def progress(self,*args):pass
                    try:
                        data,_,_ = self.catalogue._get(f'tv/{item.decision.provider_id}/season/{season}',Context())
                        for row in data.get('episodes',[]):
                            number = row.get('episode_number')
                            if type(number) is int:
                                catalogue[(season,number)] = {'episode_title':row.get('name',''),'plot':row.get('overview',''),'air_date':row.get('air_date',''),'episode_provider_id':str(row.get('id',''))}
                    except Exception:
                        plan.warnings.append(PlanIssue(code='episode_metadata_unavailable',detail='Episode catalogue unavailable; NFO uses confirmed show and filename numbers',item_id=item.id))
                metadata.update(catalogue.get((season,episode),{}))
                spec = Sidecars.episode(item,str(dst),metadata)
                projected.append((spec,Path(spec.path)))
        dependencies = [op.id for op in plan.operations if op.item_id==item.id and op.kind=='move']
        for spec,dst in projected:
            if not contained(dst,destination_root):
                plan.warnings.append(PlanIssue(code='sidecar_layout',detail='Optional output would escape the selected root; skipped',item_id=item.id))
                continue
            if dst.exists() or dst.is_symlink() or normalized(dst) in reserved:
                plan.warnings.append(PlanIssue(code='sidecar_exists',detail='Preserve existing associated output: '+str(dst),item_id=item.id))
                continue
            try:
                if spec.artwork_url:Sidecars.valid_artwork_url(spec.artwork_url)
            except ValueError:
                plan.warnings.append(PlanIssue(code='artwork_origin_unavailable',detail='Cover URL is not a supported credential-free provider origin',item_id=item.id))
                continue
            op = Operation(id=str(uuid4()),plan_id=plan.id,item_id=item.id,kind=spec.kind,source=item.path,destination=str(dst),
                expected_signature={'type':'generated','size':10*1024*1024 if spec.artwork_url else len(spec.content.encode('utf-8'))},verification={
                    'source_root':str(source_root),'destination_root':str(destination_root),'source_root_resolved':str(source_root.resolve()),'destination_root_resolved':str(destination_root.resolve()),
                    'item_signature':item.signature,'item_decision':item.decision.model_dump(),'item_path':item.path,'destination_item_path':str(item_target),
                    'content':spec.content,'artwork_url':spec.artwork_url,'dependencies':dependencies,'transfer_mode':'create',
                    'profile_id':options.profile.id,'profile_version':options.profile.version,'profile_snapshot':options.profile.model_dump()})
            plan.operations.append(op)
            reserved.add(normalized(dst))

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
            dependencies = details.get('completed_dependencies',[])
            if dependencies:
                from orion.filesystem import Filesystem
                for data in dependencies:
                    done = Operation.model_validate(data)
                    try:
                        if signature(Path(done.destination))!=done.verification['final_signature'] or Filesystem().hash(done.destination)!=done.verification['sha256']:
                            issue('target_changed','Completed media changed before optional output retry')
                    except (OSError,ValueError):issue('target_changed','Completed media is unavailable')
            if op.item_id not in checked_items:
                current_item = self.library.get(op.item_id)
                current_decision = current_item.decision.model_dump() if current_item.decision else None
                if current_decision != details.get('item_decision'):
                    issue('decision_changed','Metadata approval changed; create a new preview')
                try:
                    if not dependencies and signature(Path(details['item_path'])) != details['item_signature']:
                        issue('source_changed','Source signature changed after preview')
                except (OSError,ValueError):
                    issue('source_unavailable','Source is unavailable')
                checked_items.add(op.item_id)
            try:
                if op.kind in ('move','remove_created') and signature(src) != op.expected_signature:
                    issue('source_changed','Source file changed after preview')
            except (OSError,ValueError):
                issue('source_unavailable','Source file is unavailable')
            if op.kind != 'remove_created' and (dst.exists() or dst.is_symlink()):
                issue('destination_exists','Keep the existing file or select a different layout')
            ancestor = nearest_existing(dst.parent)
            if not ancestor.is_dir() or not os.access(ancestor,os.W_OK):
                issue('destination_access','Destination parent is not writable')
                continue
            try:
                device = ancestor.stat().st_dev
                details['transfer_mode'] = 'create' if op.kind.startswith('create_') else 'remove' if op.kind=='remove_created' else 'copy' if src.exists() and src.stat().st_dev != device else 'rename'
                if op.kind.startswith('create_') or src.exists() and src.stat().st_dev != device:
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
