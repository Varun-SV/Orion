import json
import os
import subprocess
import sys
import time
from pathlib import Path
import httpx
import pytest
from orion.launcher import InstanceLock, existing_url, available_port


def record(root,url):
    root.mkdir(exist_ok=True)
    (root/'.instance.json').write_text(json.dumps({'url':url,'pid':12345}),encoding='utf-8')


def test_unlocked_record_does_not_identify_a_live_instance(tmp_path):
    record(tmp_path,'http://127.0.0.1:54321')
    with pytest.raises(RuntimeError,match='lock|running'):
        existing_url(tmp_path)
    probe=InstanceLock(tmp_path);probe.acquire();probe.release()


def test_live_record_probe_keeps_actual_owner_locked(tmp_path):
    url='http://127.0.0.1:54321';record(tmp_path,url)
    owner=InstanceLock(tmp_path);owner.acquire()
    try:
        assert existing_url(tmp_path)==url
        with pytest.raises(RuntimeError):InstanceLock(tmp_path).acquire()
    finally:owner.release()
    with pytest.raises(RuntimeError,match='lock|running'):existing_url(tmp_path)


def launch(root,port):
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    process=subprocess.Popen([sys.executable,'-m','orion','--data-dir',str(root),'--port',str(port),'--no-browser'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=flags)
    url=f'http://127.0.0.1:{port}'
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if process.poll() is not None:pytest.fail(process.stdout.read().decode(errors='replace'))
        try:
            if httpx.get(url+'/api/v1/health',timeout=0.5).status_code==200:return process,url
        except httpx.RequestError:pass
        time.sleep(0.05)
    process.kill();process.wait(timeout=10);pytest.fail('Fixture instance did not become ready')


def test_stop_crashed_workspace_never_stops_foreign_workspace_on_reused_port(tmp_path):
    first,foreign=None,None
    crashed=tmp_path/'crashed';other=tmp_path/'other';port=available_port(0)
    try:
        first,url=launch(crashed,port)
        before=(crashed/'.instance.json').read_bytes()
        first.kill();first.wait(timeout=10)
        assert (crashed/'.instance.json').read_bytes()==before
        foreign,_=launch(other,port)
        stopped=subprocess.run([sys.executable,'-m','orion','stop','--data-dir',str(crashed)],capture_output=True,timeout=15)
        assert stopped.returncode==1,stopped.stdout.decode(errors='replace')
        assert foreign.poll() is None
        assert httpx.get(url+'/api/v1/health').status_code==200
        assert (crashed/'.instance.json').read_bytes()==before
        live_stop=subprocess.run([sys.executable,'-m','orion','stop','--data-dir',str(other)],capture_output=True,timeout=15)
        assert live_stop.returncode==0,live_stop.stderr.decode(errors='replace')
        assert foreign.wait(timeout=15)==0
    finally:
        for process in (first,foreign):
            if process is not None and process.poll() is None:process.kill();process.wait(timeout=10)


def test_stop_during_restart_checks_workspace_identity_before_shutdown(tmp_path):
    crashed=tmp_path/'restarting';other=tmp_path/'foreign';foreign=None;owner=None
    try:
        foreign,url=launch(other,available_port(0))
        record(crashed,url)
        # Real restart holds this lock while constructing its app, before its
        # newly selected port has replaced the previous instance record.
        owner=InstanceLock(crashed);owner.acquire()
        stopped=subprocess.run([sys.executable,'-m','orion','stop','--data-dir',str(crashed)],capture_output=True,timeout=15)
        assert stopped.returncode==1,stopped.stdout.decode(errors='replace')
        assert foreign.poll() is None
        assert httpx.get(url+'/api/v1/health').status_code==200
    finally:
        if owner is not None:owner.release()
        if foreign is not None and foreign.poll() is None:foreign.kill();foreign.wait(timeout=10)


def test_stop_current_workspace_through_equivalent_directory_path(tmp_path):
    root=tmp_path/'workspace with spaces';process=None
    try:
        process,_=launch(root,available_port(0))
        alias=root/'..'/root.name
        stopped=subprocess.run([sys.executable,'-m','orion','stop','--data-dir',str(alias)],capture_output=True,timeout=15)
        assert stopped.returncode==0,stopped.stderr.decode(errors='replace')
        assert process.wait(timeout=15)==0
    finally:
        if process is not None and process.poll() is None:process.kill();process.wait(timeout=10)
