from pathlib import Path
import subprocess
import sys
import hashlib
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'scripts/verify_release.py'

def cli(*args,cwd=ROOT):
    return subprocess.run([sys.executable,str(SCRIPT),*args],cwd=cwd,capture_output=True,text=True)

def git(repo,*args):
    result = subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True,text=True)
    return result.stdout.strip()

@pytest.fixture
def history(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    git(repo,'init');git(repo,'config','user.email','fixture@example.invalid');git(repo,'config','user.name','Fixture')
    (repo/'file').write_text('first');git(repo,'add','file');git(repo,'commit','-m','first')
    git(repo,'update-ref','refs/remotes/origin/main','HEAD');git(repo,'tag','v0.2.0')
    return repo

def test_tag_with_matching_version_and_main_history_passes(history):
    result=cli('--tag','v0.2.0','--version','0.2.0',cwd=history)
    assert result.returncode==0,result.stdout+result.stderr

@pytest.mark.parametrize('tag',['v0.1.0','0.2.0','v0.2.0;whoami'])
def test_version_mismatch_is_rejected(history,tag):
    result=cli('--tag',tag,'--version','0.2.0',cwd=history)
    assert result.returncode!=0
    assert 'version' in (result.stdout+result.stderr).lower()

def test_tag_outside_main_is_rejected(history):
    (history/'file').write_text('branch');git(history,'add','file');git(history,'commit','-m','outside main');git(history,'tag','v0.3.0')
    result=cli('--tag','v0.3.0','--version','0.3.0',cwd=history)
    assert result.returncode!=0
    assert 'main' in (result.stdout+result.stderr).lower()

def test_missing_main_history_is_rejected(history):
    git(history,'update-ref','-d','refs/remotes/origin/main')
    result=cli('--tag','v0.2.0','--version','0.2.0',cwd=history)
    assert result.returncode!=0
    assert 'main' in (result.stdout+result.stderr).lower()

def test_tag_must_resolve_to_checked_out_commit(history):
    (history/'file').write_text('different');git(history,'add','file');git(history,'commit','-m','different')
    result=cli('--tag','v0.2.0','--version','0.2.0',cwd=history)
    assert result.returncode!=0
    assert 'checked' in (result.stdout+result.stderr).lower()

def test_checksum_manifest_rejects_missing_tampered_and_traversal_assets(tmp_path):
    asset=tmp_path/'Orion.zip';asset.write_bytes(b'bundle')
    manifest=tmp_path/'SHA256SUMS.txt';manifest.write_text(hashlib.sha256(b'bundle').hexdigest()+'  Orion.zip\n')
    assert cli('--assets',str(tmp_path)).returncode==0
    asset.write_bytes(b'tampered')
    assert cli('--assets',str(tmp_path)).returncode!=0
    asset.unlink()
    assert cli('--assets',str(tmp_path)).returncode!=0
    manifest.write_text('0'*64+'  ../outside.zip\n')
    assert cli('--assets',str(tmp_path)).returncode!=0

def test_checksum_manifest_rejects_empty_unlisted_and_duplicate_assets(tmp_path):
    manifest=tmp_path/'SHA256SUMS.txt';manifest.write_text('')
    assert cli('--assets',str(tmp_path)).returncode!=0
    asset=tmp_path/'Orion.zip';asset.write_bytes(b'bundle')
    line=hashlib.sha256(b'bundle').hexdigest()+'  Orion.zip\n'
    manifest.write_text(line)
    (tmp_path/'unlisted.zip').write_bytes(b'other')
    assert cli('--assets',str(tmp_path)).returncode!=0
    (tmp_path/'unlisted.zip').unlink();manifest.write_text(line+line)
    assert cli('--assets',str(tmp_path)).returncode!=0


def test_archive_requires_real_executable_and_empty_output(tmp_path):
    script=ROOT/'scripts/archive_package.py'
    bundle=tmp_path/'Orion';bundle.mkdir();output=tmp_path/'release'
    result=subprocess.run([sys.executable,str(script),'--bundle',str(bundle),'--output',str(output)],capture_output=True,text=True)
    assert result.returncode!=0
    (bundle/'Orion.exe').write_bytes(b'fixture exe');(bundle/'resource.dat').write_bytes(b'fixture resource')
    result=subprocess.run([sys.executable,str(script),'--bundle',str(bundle),'--output',str(output)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert cli('--assets',str(output)).returncode==0
    import zipfile
    with zipfile.ZipFile(next(output.glob('*.zip'))) as archive:
        assert sorted(archive.namelist())==['Orion/','Orion/Orion.exe','Orion/resource.dat']
    result=subprocess.run([sys.executable,str(script),'--bundle',str(bundle),'--output',str(output)],capture_output=True,text=True)
    assert result.returncode!=0


def test_release_helper_rejects_without_explicit_draft_policy(tmp_path):
    import os
    env={**os.environ,'draft':'false'}
    result=subprocess.run([sys.executable,str(ROOT/'scripts/create_draft_release.py'),'--tag','v0.2.0','--assets',str(tmp_path)],capture_output=True,text=True,env=env)
    assert result.returncode!=0
    assert 'Draft release policy' in result.stdout
