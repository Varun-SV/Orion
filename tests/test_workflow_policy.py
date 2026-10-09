from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/check_workflows.py'

def run_policy(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, capture_output=True, text=True)

def test_repository_workflows_enforce_delivery_policy():
    result = run_policy()
    assert result.returncode == 0, result.stdout + result.stderr

@pytest.mark.parametrize('state', ['failure', 'cancelled', 'skipped', 'timed_out', ''])
def test_gate_rejects_every_unsuccessful_required_job(state):
    needs = {name: {'result': 'success'} for name in ('backend','frontend','browser','package','site')}
    needs['backend']['result'] = state
    result = run_policy('--results', json.dumps(needs))
    assert result.returncode != 0
    assert 'backend' in result.stdout

def test_gate_rejects_missing_dependency():
    result = run_policy('--results', json.dumps({'backend': {'result':'success'}}))
    assert result.returncode != 0
    assert 'frontend' in result.stdout

def test_gate_accepts_all_successes():
    needs = {name: {'result': 'success'} for name in ('backend','frontend','browser','package','site')}
    result = run_policy('--results', json.dumps(needs))
    assert result.returncode == 0, result.stdout + result.stderr

@pytest.mark.parametrize(('filename','before','after','diagnostic'), [
 ('ci.yml','pull_request:', 'pull_request_target:', 'trigger'),
 ('ci.yml','if: always()', 'if: success()', 'always'),
 ('ci.yml','contents: read', 'contents: write', 'permissions'),
 ('ci.yml','path: site/dist', 'path: .', 'site/dist'),
 ('ci.yml','timeout-minutes: 20','timeout-minutes: 0','timeout'),
 ('ci.yml','actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09','actions/checkout@v5','pinned'),
 ('ci.yml',"github.event_name == 'push' && github.ref == 'refs/heads/main'", "github.event_name == 'pull_request'", 'main'),
 ('release.yml','draft: true','draft: false','draft'),
])
def test_policy_rejects_unsafe_workflow_mutation(tmp_path, filename,before,after,diagnostic):
    workflows = ROOT / '.github/workflows'
    assert workflows.exists(), 'delivery workflows have not been implemented'
    for source in workflows.glob('*.yml'):
        (tmp_path/source.name).write_text(source.read_text(), encoding='utf-8')
    target = tmp_path/filename
    text = target.read_text()
    assert before in text
    target.write_text(text.replace(before,after), encoding='utf-8')
    result = run_policy('--directory',str(tmp_path))
    assert result.returncode != 0
    assert diagnostic in result.stdout.lower(), result.stdout

def test_policy_rejects_omitted_pages_artifact(tmp_path):
    workflows=ROOT/'.github/workflows'
    for source in workflows.glob('*.yml'):(tmp_path/source.name).write_text(source.read_text(),encoding='utf-8')
    import yaml
    target=tmp_path/'ci.yml';workflow=yaml.load(target.read_text(),Loader=yaml.BaseLoader)
    workflow['jobs']['site']['steps']=[step for step in workflow['jobs']['site']['steps'] if not step.get('uses','').startswith('actions/upload-pages-artifact@')]
    target.write_text(yaml.safe_dump(workflow),encoding='utf-8')
    result=run_policy('--directory',str(tmp_path))
    assert result.returncode!=0
    assert 'artifact' in result.stdout.lower()


def test_policy_rejects_release_guard_removed(tmp_path):
    workflows=ROOT/'.github/workflows'
    for source in workflows.glob('*.yml'):(tmp_path/source.name).write_text(source.read_text(),encoding='utf-8')
    import yaml
    target=tmp_path/'release.yml';workflow=yaml.load(target.read_text(),Loader=yaml.BaseLoader)
    workflow['jobs']['guard']['steps']=[step for step in workflow['jobs']['guard']['steps'] if 'verify_release.py' not in step.get('run','')]
    target.write_text(yaml.safe_dump(workflow),encoding='utf-8')
    result=run_policy('--directory',str(tmp_path))
    assert result.returncode!=0
    assert 'guard' in result.stdout.lower()

def test_readonly_tag_validation_has_no_nested_pages_permissions():
    import yaml
    workflow=yaml.load((ROOT/'.github/workflows/release.yml').read_text(),Loader=yaml.BaseLoader)
    assert workflow['jobs']['ci']['uses']=='./.github/workflows/validation.yml'


def test_policy_rejects_nested_permission_elevation(tmp_path):
    for source in (ROOT/'.github/workflows').glob('*.yml'):(tmp_path/source.name).write_text(source.read_text(),encoding='utf-8')
    import yaml
    path=tmp_path/'release.yml';data=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
    data['jobs']['ci']['uses']='./.github/workflows/ci.yml'
    path.write_text(yaml.safe_dump(data),encoding='utf-8')
    result=run_policy('--directory',str(tmp_path))
    assert result.returncode!=0
    assert 'permission' in result.stdout.lower()

def test_site_build_is_available_as_a_scoped_pr_review_artifact():
    import yaml
    ci=yaml.load((ROOT/'.github/workflows/ci.yml').read_text(),Loader=yaml.BaseLoader)
    previews=[step for step in ci['jobs']['site']['steps'] if step.get('with',{}).get('name')=='project-site-preview']
    assert len(previews)==1, 'PR review needs a downloadable static site build'
    assert previews[0]['with']['path']=='site/dist'
    assert previews[0]['uses'].startswith('actions/upload-artifact@')
