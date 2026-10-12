"""Reject unsafe GitHub delivery configuration and failed CI dependencies."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

REQUIRED = ('backend','frontend','browser','package','site')
MAIN = "github.event_name == 'push' && github.ref == 'refs/heads/main'"


def validate_results(needs):
    return [f'{name}: required result is {needs.get(name, {}).get("result", "missing")!r}'
            for name in REQUIRED if needs.get(name, {}).get('result') != 'success']


def validate(directory):
    import yaml
    errors=[]
    workflows={}
    for filename in ('ci.yml','pages.yml','release.yml','validation.yml'):
        path=directory/filename
        if not path.is_file():
            errors.append(f'{filename}: missing workflow');continue
        try: workflows[filename]=yaml.load(path.read_text(encoding='utf-8-sig'),Loader=yaml.BaseLoader)
        except yaml.YAMLError as exc: errors.append(f'{filename}: invalid YAML: {exc}')
    for filename,workflow in workflows.items():
        if workflow.get('permissions') != {'contents':'read'}:
            errors.append(f'{filename}: default permissions must be contents read')
        if 'pull_request_target' in workflow.get('on',{}):errors.append(f'{filename}: privileged PR trigger forbidden')
        for name,job in workflow.get('jobs',{}).items():
            if 'uses' not in job:
                try: valid=0<int(job.get('timeout-minutes','0'))<=45
                except ValueError:valid=False
                if not valid:errors.append(f'{filename}/{name}: bounded timeout required')
            if name not in ('deploy','publish') and job.get('permissions',{'contents':'read'}) != {'contents':'read'}:
                errors.append(f'{filename}/{name}: validation job permissions must be contents read')
            for step in job.get('steps',[]):
                uses=step.get('uses','')
                if uses and not uses.startswith('./') and not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?@[a-f0-9]{40}',uses):
                    errors.append(f'{filename}/{name}: external Action must be SHA pinned')
                if uses.startswith('actions/checkout@') and step.get('with',{}).get('persist-credentials')!='false':
                    errors.append(f'{filename}/{name}: checkout credentials must not persist')
    # A skipped deployment job still requests a permission ceiling when its reusable
    # workflow is called. Check every local caller chain statically.
    for filename,workflow in workflows.items():
        for name,job in workflow.get('jobs',{}).items():
            uses=job.get('uses','')
            if not uses.startswith('./.github/workflows/'):continue
            child=workflows.get(uses.rsplit('/',1)[-1],{})
            ceiling=job.get('permissions',workflow.get('permissions',{}))
            for child_name,child_job in child.get('jobs',{}).items():
                requested=child_job.get('permissions',child.get('permissions',{}))
                if any(level=='write' and ceiling.get(scope)!='write' for scope,level in requested.items()):
                    errors.append(f'{filename}/{name}: nested permission elevation in {child_name}')
    validation=workflows.get('validation.yml',{})
    if set(validation.get('on',{}))!={'workflow_call'} or set(validation.get('jobs',{}))!=set((*REQUIRED,'gate')):
        errors.append('validation: read-only reusable jobs only required')
    import copy
    for name in (*REQUIRED,'gate'):
        direct=copy.deepcopy(workflows.get('ci.yml',{}).get('jobs',{}).get(name,{}))
        direct['steps']=[step for step in direct.get('steps',[]) if not step.get('uses','').startswith('actions/upload-pages-artifact@')]
        if direct!=validation.get('jobs',{}).get(name):errors.append(f'validation: required job drift in {name}')
    ci=workflows.get('ci.yml',{});jobs=ci.get('jobs',{});events=ci.get('on',{})
    if set(events)!= {'pull_request','push','workflow_call'}:errors.append('ci: required trigger events absent or unexpected')
    if events.get('pull_request',{}).get('branches') != ['main'] or any(key in events.get('pull_request',{}) for key in ('paths','paths-ignore')):
        errors.append('ci: PR trigger must cover every change to main')
    if events.get('push',{}).get('branches') != ['main']:errors.append('ci: push trigger must be main')
    gate=jobs.get('gate',{})
    if gate.get('name')!='CI' or gate.get('if')!='always()':errors.append('ci gate: CI must run with always()')
    if set(gate.get('needs',[]))!=set(REQUIRED):errors.append('ci gate: all required job dependencies needed')
    gate_command=' '.join(step.get('run','') for step in gate.get('steps',[]))
    if 'scripts/check_workflows.py --results' not in gate_command or '${{ toJSON(needs) }}' not in str(gate):errors.append('ci gate: must validate actual dependency results')
    for name in REQUIRED:
        if name not in jobs:errors.append(f'ci: {name} job missing')
    site_steps=jobs.get('site',{}).get('steps',[])
    preview=[step for step in site_steps if step.get('with',{}).get('name')=='project-site-preview']
    if len(preview)!=1 or preview[0].get('with',{}).get('path')!='site/dist' or not preview[0].get('uses','').startswith('actions/upload-artifact@'):
        errors.append('ci: PR site review artifact must contain only site/dist')
    if not any(step.get('uses','').startswith('actions/upload-pages-artifact@') for step in site_steps):errors.append('ci: Pages artifact upload missing')
    for step in site_steps:
        if step.get('uses','').startswith('actions/upload-pages-artifact@'):
            if step.get('with',{}).get('path')!='site/dist':errors.append('ci: Pages artifact must be site/dist')
            if step.get('if')!=MAIN:errors.append('ci: Pages upload must be main push only')
    deploy=jobs.get('deploy',{})
    if deploy.get('uses')!='./.github/workflows/pages.yml' or deploy.get('needs')!='gate' or deploy.get('if')!=MAIN:
        errors.append('ci: Pages deploy must need gate and run on main push only')
    pages=workflows.get('pages.yml',{})
    if set(pages.get('on',{}))!={'workflow_call'}:errors.append('pages: reusable workflow trigger only')
    page_job=pages.get('jobs',{}).get('deploy',{})
    if page_job.get('if')!=MAIN or page_job.get('environment',{}).get('name')!='github-pages':errors.append('pages: main guard and github-pages environment required')
    allowed={'contents':'read','pages':'write','id-token':'write'}
    if page_job.get('permissions')!=allowed or deploy.get('permissions')!=allowed:errors.append('pages: only scoped Pages permissions allowed')
    release=workflows.get('release.yml',{})
    if release.get('on')!={'push':{'tags':['v*']}}:errors.append('release: tag-only trigger required')
    release_jobs=release.get('jobs',{})
    guard=release_jobs.get('guard',{})
    if not any('scripts/verify_release.py --tag' in step.get('run','') and '--version' in step.get('run','') for step in guard.get('steps',[])):errors.append('release: version and ancestry guard missing')
    if not any(step.get('uses','').startswith('actions/checkout@') and step.get('with',{}).get('fetch-depth')=='0' for step in guard.get('steps',[])):errors.append('release: guard requires complete history')
    if release_jobs.get('ci',{}).get('uses')!='./.github/workflows/validation.yml' or release_jobs.get('ci',{}).get('needs')!='guard':errors.append('release: CI must follow the guard at tagged commit')
    publish=release_jobs.get('publish',{})
    if set(publish.get('needs',[]))!={'ci','guard','package'}:errors.append('release: publishing must require guard CI and package')
    if publish.get('permissions')!={'contents':'write'}:errors.append('release: publish permission must be scoped')
    steps=publish.get('steps',[])
    # The source-controlled release helper forces --draft; YAML input makes policy review explicit.
    drafts=[step for step in steps if step.get('env',{}).get('draft')=='true']
    if not drafts or not any('scripts/create_draft_release.py' in step.get('run','') for step in drafts):errors.append('release: draft release creation required')
    return errors


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parents[1]/'.github/workflows');parser.add_argument('--results')
    args=parser.parse_args()
    try:errors=validate_results(json.loads(args.results)) if args.results is not None else validate(args.directory)
    except (ValueError,TypeError,AttributeError) as exc:errors=[f'Invalid policy input: {exc}']
    for error in errors:print(error)
    if not errors:print('Delivery policy passed.')
    return bool(errors)

if __name__=='__main__':raise SystemExit(main())

