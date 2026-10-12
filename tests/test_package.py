from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_build_preflight_rejects_missing_frontend_resources(tmp_path):
    result=subprocess.run([sys.executable,str(ROOT/'scripts/build_package.py'),'--validate-only','--frontend',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode!=0
    assert 'index.html' in result.stdout+result.stderr

def test_build_preflight_accepts_production_index_and_assets(tmp_path):
    (tmp_path/'assets').mkdir();(tmp_path/'assets/app.js').write_text('console.log("Orion")')
    (tmp_path/'index.html').write_text('<html><script src="/assets/app.js"></script></html>')
    result=subprocess.run([sys.executable,str(ROOT/'scripts/build_package.py'),'--validate-only','--frontend',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr

@pytest.mark.skipif(not os.environ.get('ORION_PACKAGE_EXE'),reason='real bundle smoke runs in Windows package job')
def test_windows_bundle_starts_serves_isolated_data_handles_ports_and_stops(tmp_path):
    result=subprocess.run([sys.executable,str(ROOT/'scripts/smoke_package.py'),'--executable',os.environ['ORION_PACKAGE_EXE'],'--output',str(tmp_path/'smoke.json')],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout+result.stderr

def test_build_preflight_rejects_missing_index_asset(tmp_path):
    (tmp_path/'assets').mkdir();(tmp_path/'assets/other.js').write_text('console.log("other")')
    (tmp_path/'index.html').write_text('<html><script src="/assets/missing.js"></script></html>')
    result=subprocess.run([sys.executable,str(ROOT/'scripts/build_package.py'),'--validate-only','--frontend',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode!=0
    assert 'missing.js' in result.stdout+result.stderr
